"""처방 등록(scan) DB 연결 — scan_service.ScanRepo의 Tortoise 구현. 담당: AI A 채민

- conn을 받는 메서드는 그 트랜잭션 안에서 실행합니다(확정·취소·다시 고르기처럼 "잠그고 확인 후 바꾸기").
- 읽기 작업이 끝날 때 상태를 바꾸는 메서드(finish_ocr_done/failed)는 "아직 uploaded일 때만" 바꾸는
  조건부 UPDATE라서, 그사이 회원이 취소(expired)하거나 시간 초과로 바뀐 문서를 덮어쓰지 않습니다.
- parsed_result·masked_lines는 JSON 글자로 저장합니다. 명세상 마스킹 후 암호화 대상이라,
  암호화 공용 함수가 생기면 _encode/_decode 두 곳만 바꾸면 됩니다.
- 시각은 tortoise.timezone.now()와 같은 기준으로 넘겨 주세요(Deps.now).
"""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from tortoise.expressions import Q
from tortoise.transactions import in_transaction

from app.dtos.scan import DocType, DocumentStatus, FailReason, ScanStep
from app.models.documents import DocumentPage, MedicalDocument
from app.models.prescriptions import Prescription
from app.services.scan_service import IMAGE_TTL, ScanDoc, ScanStateError

OPEN_STATUSES = (DocumentStatus.UPLOADED, DocumentStatus.OCR_DONE, DocumentStatus.OCR_FAILED)


@dataclass(frozen=True)
class NewPage:
    """document_pages 한 행. 파일은 FileStore로 먼저 저장하고 그 경로를 넣습니다."""

    page_no: int
    original_name: str | None
    mime_type: str
    file_size_bytes: int
    file_hash: str  # 원본 파일 SHA-256
    file_path: str  # 원본 파일(PDF면 여러 페이지가 같은 경로)
    image_path: str  # OCR·원본 보기용 페이지 이미지
    source_page_no: int = 1  # 원본 파일 안의 페이지(PDF), 이미지는 1


def _encode(value: Any) -> str:
    # TODO(암호화 공용 함수): 마스킹 후 암호화(NFR-004)
    return json.dumps(value, ensure_ascii=False)


def _decode(text: str | None) -> Any:
    return None if text is None else json.loads(text)


class ScanRepository:
    """scan_service.ScanRepo 구현.

    read_file: 페이지 이미지 경로 → 바이트(FileStore). 로컬 폴더/S3는 FileStore가 정합니다.
    """

    def __init__(self, read_file: Callable[[str], Awaitable[bytes]] | None = None) -> None:
        self._read_file = read_file

    # ------------------------------------------------------------------
    # 트랜잭션·조회
    # ------------------------------------------------------------------
    def transaction(self):
        return in_transaction()

    async def get(self, scan_id: int, *, for_update: bool = False, conn: Any = None) -> ScanDoc:
        query = MedicalDocument.filter(id=scan_id)
        if conn is not None:
            query = query.using_db(conn)
        if for_update:
            query = query.select_for_update()
        doc = await query.first()
        if doc is None:
            raise ScanStateError("NOT_FOUND")
        return await self._to_scan_doc(doc, conn)

    async def _to_scan_doc(self, doc: MedicalDocument, conn: Any = None) -> ScanDoc:
        pages = DocumentPage.filter(document_id=doc.id)
        prescriptions = Prescription.filter(document_id=doc.id)
        if conn is not None:
            pages, prescriptions = pages.using_db(conn), prescriptions.using_db(conn)
        page_count = await pages.count()
        pages_left = await pages.filter(deleted_at__isnull=True).exists()
        prescription_id = await prescriptions.first().values_list("id", flat=True)
        return ScanDoc(
            scan_id=doc.id,
            user_id=doc.user_id,  # type: ignore[attr-defined]
            status=DocumentStatus(doc.status),
            step=ScanStep(doc.step) if doc.step else None,
            doc_type=DocType(doc.doc_type),
            processing_started_at=doc.processing_started_at or doc.created_at,
            image_delete_due_at=doc.image_delete_due_at,
            page_count=page_count,
            fail_reason=FailReason(doc.fail_reason) if doc.fail_reason else None,
            parsed_result=_decode(doc.parsed_result),
            prescription_id=prescription_id,
            pages_left=pages_left,
        )

    # ------------------------------------------------------------------
    # POST /scans
    # ------------------------------------------------------------------
    async def count_scans_since(self, user_id: int, since: datetime) -> int:
        """하루 올린 횟수(6장 하루 20회). 취소·만료(expired)된 문서도 셉니다."""
        return await MedicalDocument.filter(user_id=user_id, created_at__gte=since).count()

    async def create_scan(self, user_id: int, doc_type: DocType, now: datetime, pages: list[NewPage]) -> ScanDoc:
        """문서 + 페이지 행을 한 트랜잭션으로 만듭니다(uploaded / reading, 업로드 + 3시간 뒤 삭제)."""
        async with in_transaction() as conn:
            doc = await MedicalDocument.create(
                user_id=user_id,
                doc_type=doc_type.value,
                status=DocumentStatus.UPLOADED.value,
                step=ScanStep.READING.value,
                image_delete_due_at=now + IMAGE_TTL,
                processing_started_at=now,
                using_db=conn,
            )
            await DocumentPage.bulk_create(
                [
                    DocumentPage(
                        document_id=doc.id,
                        page_no=p.page_no,
                        original_name=p.original_name,
                        mime_type=p.mime_type,
                        file_size_bytes=p.file_size_bytes,
                        file_hash=p.file_hash,
                        file_path=p.file_path,
                        source_page_no=p.source_page_no,
                        image_path=p.image_path,
                    )
                    for p in pages
                ],
                using_db=conn,
            )
            return await self._to_scan_doc(doc, conn)

    # ------------------------------------------------------------------
    # 읽기 작업(run_scan_job)
    # ------------------------------------------------------------------
    async def set_step(self, scan_id: int, step: ScanStep) -> None:
        await MedicalDocument.filter(id=scan_id, status=DocumentStatus.UPLOADED.value).update(step=step.value)

    async def finish_ocr_done(self, scan_id: int, parsed_result: dict) -> bool:
        updated = await MedicalDocument.filter(id=scan_id, status=DocumentStatus.UPLOADED.value).update(
            status=DocumentStatus.OCR_DONE.value, step=None, fail_reason=None, parsed_result=_encode(parsed_result)
        )
        return updated > 0

    async def finish_ocr_failed(self, scan_id: int, reason: FailReason) -> bool:
        updated = await MedicalDocument.filter(id=scan_id, status=DocumentStatus.UPLOADED.value).update(
            status=DocumentStatus.OCR_FAILED.value, step=None, fail_reason=reason.value
        )
        return updated > 0

    async def page_images(self, scan_id: int) -> list[tuple[int, bytes]]:
        if self._read_file is None:
            raise RuntimeError("ScanRepository에 read_file(FileStore)이 연결되지 않았어요")
        pages = (
            await DocumentPage.filter(document_id=scan_id, deleted_at__isnull=True)
            .order_by("page_no")
            .values_list("page_no", "image_path")
        )
        return [(page_no, await self._read_file(path)) for page_no, path in pages]

    async def save_masked_lines(self, scan_id: int, lines: list[dict]) -> None:
        await MedicalDocument.filter(id=scan_id).update(masked_lines=_encode(lines))

    async def load_masked_lines(self, scan_id: int) -> list[dict]:
        text = await MedicalDocument.filter(id=scan_id).first().values_list("masked_lines", flat=True)
        return _decode(text) or []

    # ------------------------------------------------------------------
    # PATCH /scans (고친 값 저장·문서 종류 다시 고르기)
    # ------------------------------------------------------------------
    async def save_parsed_result(self, scan_id: int, parsed_result: dict) -> None:
        await MedicalDocument.filter(id=scan_id).update(parsed_result=_encode(parsed_result))

    async def set_reprocessing(self, scan_id: int, doc_type: DocType, now: datetime, *, conn: Any = None) -> None:
        """문서 종류를 다시 골라 정리만 다시 함: uploaded / structuring, 90초 기준 시각을 지금으로."""
        query = MedicalDocument.filter(id=scan_id)
        if conn is not None:
            query = query.using_db(conn)
        await query.update(
            doc_type=doc_type.value,
            status=DocumentStatus.UPLOADED.value,
            step=ScanStep.STRUCTURING.value,
            processing_started_at=now,
            parsed_result=None,
            fail_reason=None,
        )

    # ------------------------------------------------------------------
    # 취소·만료·정리
    # ------------------------------------------------------------------
    async def expire(self, scan_id: int, *, conn: Any = None) -> None:
        """status=expired, 인식 결과·가린 줄 비우기(NFR-004). 행은 남겨 하루 20회에 셈."""
        query = MedicalDocument.filter(id=scan_id)
        if conn is not None:
            query = query.using_db(conn)
        await query.update(status=DocumentStatus.EXPIRED.value, step=None, parsed_result=None, masked_lines=None)

    async def mark_pages_deleted(self, scan_id: int, now: datetime) -> None:
        await DocumentPage.filter(document_id=scan_id, deleted_at__isnull=True).update(deleted_at=now)

    async def cleanup_candidates(self, now: datetime) -> list[ScanDoc]:
        """정리 작업 후보: 3시간 지난 미확정 문서, 또는 확정·만료됐는데 사진이 남은 문서."""
        due = Q(status__in=[s.value for s in OPEN_STATUSES], image_delete_due_at__lte=now)
        closed_with_pages = Q(
            status__in=[DocumentStatus.CONFIRMED.value, DocumentStatus.EXPIRED.value],
            pages__deleted_at__isnull=True,
        )
        docs = await MedicalDocument.filter(due | closed_with_pages).distinct()
        return [await self._to_scan_doc(d) for d in docs]


KST = timezone(timedelta(hours=9))  # 한국은 서머타임이 없어 고정 +9시간(Windows에서 tzdata 없이도 동작)


def kst_day_start(now: datetime) -> datetime:
    """하루 20회를 셀 '오늘'의 시작(한국 시간 자정)."""
    if now.tzinfo is None:  # Tortoise use_tz=False면 이미 Asia/Seoul 기준의 시간대 없는 시각
        return now.replace(hour=0, minute=0, second=0, microsecond=0)
    return now.astimezone(KST).replace(hour=0, minute=0, second=0, microsecond=0)
