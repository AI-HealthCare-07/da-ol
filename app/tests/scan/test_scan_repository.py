"""scan_repository(DB) 테스트. conftest의 테스트 DB를 씁니다(docker compose의 db가 켜져 있어야 함)."""

from datetime import UTC, timedelta

from tortoise import timezone
from tortoise.contrib.test import TestCase

import app.services.scan_service as sp
from app.dtos.scan import DocType, DocumentStatus, FailReason, ScanStep
from app.models.documents import DocumentPage, MedicalDocument
from app.models.enums import PrescriptionSource
from app.models.prescriptions import Prescription
from app.models.users import User
from app.repositories.scan_repository import KST, NewPage, ScanRepository, kst_day_start
from app.tests.scan.fakes import GOOD_LLM, FakeCatalog, FakeFiles, FakeInstructions, FakeLlm, FakeOcr


def new_page(page_no: int, **kw) -> NewPage:
    return NewPage(
        page_no=page_no,
        original_name=kw.get("original_name", f"p{page_no}.png"),
        mime_type=kw.get("mime_type", "image/png"),
        file_size_bytes=kw.get("file_size_bytes", 100),
        file_hash=kw.get("file_hash", "0" * 64),
        file_path=kw.get("file_path", f"scans/{page_no}.png"),
        image_path=kw.get("image_path", f"scans/{page_no}.png"),
        source_page_no=kw.get("source_page_no", 1),
    )


class ScanRepositoryTest(TestCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.user = await User.create(kakao_id="kakao-scan-repo", nickname="스캔테스터")
        self.files: dict[str, bytes] = {}

        async def read_file(path: str) -> bytes:
            return self.files[path]

        self.repo = ScanRepository(read_file=read_file)
        self.now = timezone.now()

    async def create(self, pages: int = 2, **kw):
        return await self.repo.create_scan(
            self.user.id, kw.get("doc_type", DocType.PRESCRIPTION), kw.get("now", self.now),
            [new_page(i + 1) for i in range(pages)],
        )  # fmt: skip

    # ---- 만들기·조회 ---------------------------------------------------------
    async def test_create_scan(self):
        doc = await self.create(pages=3)
        assert doc.status == DocumentStatus.UPLOADED and doc.step == ScanStep.READING
        assert doc.user_id == self.user.id and doc.doc_type == DocType.PRESCRIPTION
        assert doc.page_count == 3 and doc.pages_left
        assert doc.processing_started_at == self.now
        assert doc.image_delete_due_at == self.now + sp.IMAGE_TTL
        assert doc.parsed_result is None and doc.fail_reason is None and doc.prescription_id is None
        pages = await DocumentPage.filter(document_id=doc.scan_id).order_by("page_no").values_list("page_no", flat=True)
        assert pages == [1, 2, 3]

    async def test_pdf_pages_share_original_file(self):
        doc = await self.repo.create_scan(
            self.user.id,
            DocType.PRESCRIPTION,
            self.now,
            [new_page(i + 1, file_path="scans/a.pdf", image_path=f"scans/a-{i + 1}.png", source_page_no=i + 1)
             for i in range(2)],
        )  # fmt: skip
        rows = await DocumentPage.filter(document_id=doc.scan_id).order_by("page_no")
        assert [(r.file_path, r.source_page_no, r.image_path) for r in rows] == [
            ("scans/a.pdf", 1, "scans/a-1.png"),
            ("scans/a.pdf", 2, "scans/a-2.png"),
        ]

    async def test_get_not_found(self):
        with self.assertRaises(sp.ScanStateError) as e:
            await self.repo.get(999_999)
        assert e.exception.code == "NOT_FOUND"

    async def test_get_for_update_in_transaction(self):
        doc = await self.create()
        async with self.repo.transaction() as conn:
            locked = await self.repo.get(doc.scan_id, for_update=True, conn=conn)
            await self.repo.expire(doc.scan_id, conn=conn)
        assert locked.status == DocumentStatus.UPLOADED
        assert (await self.repo.get(doc.scan_id)).status == DocumentStatus.EXPIRED

    async def test_prescription_id_from_linked_prescription(self):
        doc = await self.create()
        p = await Prescription.create(user=self.user, source=PrescriptionSource.OCR, document_id=doc.scan_id)
        assert (await self.repo.get(doc.scan_id)).prescription_id == p.id

    # ---- 하루 20회 ----------------------------------------------------------
    async def test_count_scans_since_includes_expired(self):
        first = await self.create()
        await self.create()
        await self.repo.expire(first.scan_id)
        other = await User.create(kakao_id="kakao-other", nickname="다른회원")
        await self.repo.create_scan(other.id, DocType.PRESCRIPTION, self.now, [new_page(1)])
        assert await self.repo.count_scans_since(self.user.id, self.now - timedelta(minutes=1)) == 2
        assert await self.repo.count_scans_since(self.user.id, self.now + timedelta(minutes=1)) == 0

    # ---- 읽기 작업 ----------------------------------------------------------
    async def test_finish_ocr_done_only_while_uploaded(self):
        doc = await self.create()
        await self.repo.set_step(doc.scan_id, ScanStep.STRUCTURING)
        assert (await self.repo.get(doc.scan_id)).step == ScanStep.STRUCTURING
        assert await self.repo.finish_ocr_done(doc.scan_id, {"drugs": [{"line_no": 1}], "masked": True})
        got = await self.repo.get(doc.scan_id)
        assert got.status == DocumentStatus.OCR_DONE and got.step is None
        assert got.parsed_result == {"drugs": [{"line_no": 1}], "masked": True}
        # 이미 끝난 문서는 다시 바꾸지 않음
        assert not await self.repo.finish_ocr_failed(doc.scan_id, FailReason.TIMEOUT)
        assert (await self.repo.get(doc.scan_id)).status == DocumentStatus.OCR_DONE

    async def test_finish_does_not_overwrite_expired(self):
        doc = await self.create()
        await self.repo.expire(doc.scan_id)  # 읽는 중에 회원이 취소
        assert not await self.repo.finish_ocr_done(doc.scan_id, {"drugs": []})
        assert not await self.repo.finish_ocr_failed(doc.scan_id, FailReason.OCR_ERROR)
        await self.repo.set_step(doc.scan_id, ScanStep.STRUCTURING)
        got = await self.repo.get(doc.scan_id)
        assert got.status == DocumentStatus.EXPIRED and got.parsed_result is None and got.step is None

    async def test_finish_ocr_failed(self):
        doc = await self.create()
        assert await self.repo.finish_ocr_failed(doc.scan_id, FailReason.NO_TEXT)
        got = await self.repo.get(doc.scan_id)
        assert got.status == DocumentStatus.OCR_FAILED and got.fail_reason == FailReason.NO_TEXT

    async def test_masked_lines_round_trip_and_cleared_on_expire(self):
        doc = await self.create()
        lines = [{"page_no": 1, "line_idx": 0, "words": [["[이름]", 0.99], ["귀하", 1.0]]}]
        assert await self.repo.load_masked_lines(doc.scan_id) == []
        await self.repo.save_masked_lines(doc.scan_id, lines)
        assert await self.repo.load_masked_lines(doc.scan_id) == lines
        await self.repo.finish_ocr_done(doc.scan_id, {"drugs": []})
        await self.repo.expire(doc.scan_id)
        row = await MedicalDocument.get(id=doc.scan_id)
        assert row.masked_lines is None and row.parsed_result is None  # NFR-004

    async def test_page_images_in_order_and_skip_deleted(self):
        doc = await self.create(pages=3)
        self.files = {"scans/1.png": b"one", "scans/2.png": b"two", "scans/3.png": b"three"}
        assert await self.repo.page_images(doc.scan_id) == [(1, b"one"), (2, b"two"), (3, b"three")]
        await self.repo.mark_pages_deleted(doc.scan_id, self.now)
        assert await self.repo.page_images(doc.scan_id) == []
        assert not (await self.repo.get(doc.scan_id)).pages_left

    # ---- PATCH ------------------------------------------------------------
    async def test_save_parsed_result_and_reprocessing(self):
        doc = await self.create()
        await self.repo.finish_ocr_failed(doc.scan_id, FailReason.NO_DRUG_FOUND)
        later = self.now + timedelta(minutes=5)
        await self.repo.set_reprocessing(doc.scan_id, DocType.PILL_ENVELOPE, later)
        got = await self.repo.get(doc.scan_id)
        assert (got.status, got.step, got.doc_type) == (
            DocumentStatus.UPLOADED, ScanStep.STRUCTURING, DocType.PILL_ENVELOPE,
        )  # fmt: skip
        assert got.fail_reason is None and got.processing_started_at == later
        await self.repo.save_parsed_result(doc.scan_id, {"edited": True})
        assert (await self.repo.get(doc.scan_id)).parsed_result == {"edited": True}

    # ---- 정리 작업 ----------------------------------------------------------
    async def test_cleanup_candidates(self):
        due = await self.create(now=self.now - timedelta(hours=4))  # 3시간 지난 미확정
        fresh = await self.create()  # 아직 3시간 안 됨
        confirmed = await self.create()
        await MedicalDocument.filter(id=confirmed.scan_id).update(status=DocumentStatus.CONFIRMED.value)
        cleaned = await self.create()
        await MedicalDocument.filter(id=cleaned.scan_id).update(status=DocumentStatus.CONFIRMED.value)
        await self.repo.mark_pages_deleted(cleaned.scan_id, self.now)

        ids = {d.scan_id for d in await self.repo.cleanup_candidates(self.now)}
        assert due.scan_id in ids and confirmed.scan_id in ids
        assert fresh.scan_id not in ids and cleaned.scan_id not in ids

    async def test_cleanup_skips_closed_document_without_pages(self):
        # 시드처럼 페이지 행 없이 만들어진 확정·만료 문서는 지울 사진이 없으므로 후보가 아님 (#96 리뷰)
        no_pages = []
        for status in (DocumentStatus.CONFIRMED, DocumentStatus.EXPIRED):
            doc = await MedicalDocument.create(
                user=self.user,
                doc_type=DocType.PRESCRIPTION.value,
                status=status.value,
                image_delete_due_at=self.now - timedelta(hours=4),
            )
            no_pages.append(doc.id)
        ids = {d.scan_id for d in await self.repo.cleanup_candidates(self.now)}
        assert not ids & set(no_pages)

    async def test_run_cleanup_with_real_repo(self):
        due = await self.create(now=self.now - timedelta(hours=4))
        deps = self.deps()
        await sp.run_cleanup(deps, await self.repo.cleanup_candidates(self.now))
        got = await self.repo.get(due.scan_id)
        assert got.status == DocumentStatus.EXPIRED and not got.pages_left

    # ---- run_scan_job을 실제 DB로 -------------------------------------------
    def deps(self) -> sp.Deps:
        return sp.Deps(
            repo=self.repo,
            ocr=FakeOcr(),
            llm=FakeLlm((GOOD_LLM,)),
            catalog=FakeCatalog(),
            instructions=FakeInstructions(),
            files=FakeFiles(),
            now=timezone.now,
        )

    async def test_run_scan_job_with_real_repo(self):
        doc = await self.create(pages=1)
        self.files = {"scans/1.png": b"\x89PNG\r\n\x1a\nfake"}
        await sp.run_scan_job(self.deps(), doc.scan_id)
        got = await self.repo.get(doc.scan_id)
        assert got.status == DocumentStatus.OCR_DONE, got.fail_reason
        assert got.parsed_result["drugs"]
        assert await self.repo.load_masked_lines(doc.scan_id)  # 문서 종류를 다시 고를 때 쓸 가린 줄


def test_kst_day_start():
    from datetime import datetime

    # UTC 11/26 15:30 = 한국 11/27 00:30 → 한국 기준 11/27 00:00
    start = kst_day_start(datetime(2026, 11, 26, 15, 30, tzinfo=UTC))
    assert start == datetime(2026, 11, 27, 0, 0, tzinfo=KST)
    # 시간대 없는 시각은 이미 한국 시간으로 봄
    assert kst_day_start(datetime(2026, 11, 27, 13, 5)) == datetime(2026, 11, 27, 0, 0)
