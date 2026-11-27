"""scan_service.py 테스트. CLOVA·LLM·DB는 가짜로 바꿔 끼워 파이프라인을 끝까지 실행합니다.
비동기 함수는 run()(asyncio.run)으로 실행해서 별도 플러그인 없이 돌아갑니다.
프로젝트에 pytest-asyncio가 있으면 async def 테스트로 바꿔도 됩니다."""

import asyncio
import json
from dataclasses import replace
from datetime import timedelta
from pathlib import Path

import pytest
from pydantic import TypeAdapter

import app.services.scan_service as sp
from app.dtos.scan import (
    DocType,
    DocumentStatus,
    FailReason,
    ScanOcrDoneResponse,
    ScanStatusResponse,
    ScanStep,
)
from app.tests.scan.fakes import (
    GOOD_LLM,
    NOW,
    FakeCatalog,
    FakeFiles,
    FakeOcr,
    W,
    edit,
    fill_meals_passthrough,
    make_deps,
    new_doc,
    run,
)


# ---------------------------------------------------------------------------
# 가리기
# ---------------------------------------------------------------------------
def test_mask_line_across_words_keeps_confidence():
    line = sp.make_line(1, 0, [W("성명", 0.99), W("홍길동", 0.6), W("010-1234-5678", 0.9)])
    masked = sp.mask_line(line)
    assert [w.text for w in masked.words] == ["성명", "[이름]", "[연락처]"]
    assert [w.confidence for w in masked.words] == [0.99, 0.6, 0.9]
    assert masked.text == "성명 [이름] [연락처]"


def test_mask_line_span_over_several_words():
    line = sp.make_line(1, 0, [W("900101", 0.9), W("-", 0.9), W("1234567", 0.9), W("약", 0.9)])
    assert sp.mask_line(line).text == "[주민번호] 약"


# ---------------------------------------------------------------------------
# 읽기 작업 끝까지
# ---------------------------------------------------------------------------
def test_job_success_end_to_end():
    deps = make_deps()
    run(sp.run_scan_job(deps, 42))
    doc = deps.repo.doc
    assert doc.status == DocumentStatus.OCR_DONE and doc.step is None

    # LLM에는 가린 줄만 갔음
    sent = "\n".join(deps.llm.seen[0])
    assert "홍길동" not in sent and "900101" not in sent and "[이름]" in sent
    assert sent.splitlines()[0].startswith("[p1-l0]")

    # 원문 줄 순서대로 정렬, line_no 다시 매김
    drugs = doc.parsed_result["drugs"]
    assert [d["drug_name"]["value"] for d in drugs] == ["가상정5mg", "가상캡슐"]
    assert [d["line_no"] for d in drugs] == [1, 2]

    first = drugs[0]
    assert first["times_per_day"] == {"value": 3, "confidence": 0.72, "needs_check": True}  # 0.8 미만
    assert first["total_days"]["confidence"] == 0.94  # 약 이름 속 '5mg'이 아니라 일수 칸의 5
    assert first["dose_per_time"]["min"] == 1 and first["dose_per_time"]["needs_check"] is False
    assert first["match"]["status"] == "exact" and first["is_oral"] is True
    assert first["dosage"]["needs_confirm"] is False
    assert drugs[1]["dosage"]["needs_confirm"] is True  # 복용 조건 없음 → 확인 필요

    # 날짜는 2026.11.20 → 2026-11-20 으로 형태가 바뀌어도 숫자가 같으면 원문 신뢰도
    assert doc.parsed_result["prescribed_date"] == {"value": "2026-11-20", "confidence": 0.93, "needs_check": False}

    # GET 응답이 계약과 맞음
    resp = run(sp.get_scan(deps, 42, fill_default_meals=fill_meals_passthrough))
    assert isinstance(resp, ScanOcrDoneResponse)
    TypeAdapter(ScanStatusResponse).validate_python(resp.model_dump(mode="json"))


def test_changed_value_has_no_confidence():
    llm = json.loads(json.dumps(GOOD_LLM))
    llm["drugs"][1]["drug_name"] = "가상정 5mg"  # 띄어쓰기만 다르면 같은 값으로 봄
    llm["drugs"][0]["drug_name"] = "가상캡슐250"  # 원문에 없는 글자 → 바뀐 값
    deps = make_deps([llm])
    run(sp.run_scan_job(deps, 42))
    by_name = {d["line_no"]: d["drug_name"] for d in deps.repo.doc.parsed_result["drugs"]}
    assert by_name[1]["confidence"] == 0.91
    assert by_name[2] == {"value": "가상캡슐250", "confidence": None, "needs_check": True}


@pytest.mark.parametrize("fail_times, status", [(2, DocumentStatus.OCR_DONE), (3, DocumentStatus.OCR_FAILED)])
def test_ocr_retry_twice(fail_times, status):
    deps = make_deps(ocr=FakeOcr(fail_times=fail_times))
    run(sp.run_scan_job(deps, 42))
    assert deps.repo.doc.status == status
    if status == DocumentStatus.OCR_FAILED:
        assert deps.repo.doc.fail_reason == FailReason.OCR_ERROR


def test_llm_retry_once_then_structure_error():
    assert_reason(make_deps(["not json", "```json\n{bad}\n```"]), FailReason.STRUCTURE_ERROR)
    deps = make_deps(["not json", GOOD_LLM])
    run(sp.run_scan_job(deps, 42))
    assert deps.repo.doc.status == DocumentStatus.OCR_DONE


def test_no_drug_found():
    assert_reason(make_deps([{"hospital_name": None, "drugs": []}]), FailReason.NO_DRUG_FOUND)


def test_no_text():
    class Blank(FakeOcr):
        async def read_page(self, image):
            return [sp.make_line(0, 0, [W("흐림", 0.2)])]

    assert_reason(make_deps(ocr=Blank()), FailReason.NO_TEXT)


def test_timeout_during_job():
    deps = make_deps(doc=new_doc(processing_started_at=NOW - timedelta(seconds=91)))
    assert_reason(deps, FailReason.TIMEOUT)


def test_cancel_during_job_discards_result():
    deps = make_deps()
    deps.repo.expire_after_reads = 2  # 읽기 도중 취소됨
    run(sp.run_scan_job(deps, 42))
    assert deps.repo.doc.status == DocumentStatus.EXPIRED
    assert deps.repo.doc.parsed_result is None


def assert_reason(deps, reason):
    run(sp.run_scan_job(deps, 42))
    assert deps.repo.doc.status == DocumentStatus.OCR_FAILED
    assert deps.repo.doc.fail_reason == reason


# ---------------------------------------------------------------------------
# GET 시간 초과, 문서 종류 다시 고르기
# ---------------------------------------------------------------------------
def test_get_marks_timeout_when_job_stalled():
    deps = make_deps(doc=new_doc(processing_started_at=NOW - timedelta(seconds=120)))
    resp = run(sp.get_scan(deps, 42, fill_default_meals=fill_meals_passthrough))
    assert resp.status == DocumentStatus.OCR_FAILED and resp.fail_reason == FailReason.TIMEOUT
    assert resp.message.startswith("인식에 실패했어요")


@pytest.mark.parametrize(
    "status, reason, ok",
    [
        (DocumentStatus.OCR_DONE, None, True),
        (DocumentStatus.OCR_FAILED, FailReason.NO_DRUG_FOUND, True),
        (DocumentStatus.OCR_FAILED, FailReason.STRUCTURE_ERROR, True),
        (DocumentStatus.OCR_FAILED, FailReason.NO_TEXT, False),
        (DocumentStatus.UPLOADED, None, False),
    ],
)
def test_can_repick(status, reason, ok):
    assert sp.can_repick_doc_type(new_doc(status=status, fail_reason=reason)) is ok


def test_repick_reuses_masked_lines_without_ocr():
    deps = make_deps(llm_responses=(GOOD_LLM, GOOD_LLM))
    run(sp.run_scan_job(deps, 42))
    ocr_calls = deps.ocr.calls
    scheduled = []
    run(sp.repick_doc_type(deps, 42, DocType.PILL_ENVELOPE, schedule=lambda fn, *a, **k: scheduled.append((fn, a, k))))
    assert deps.repo.doc.status == DocumentStatus.UPLOADED and deps.repo.doc.step == ScanStep.STRUCTURING
    fn, a, k = scheduled[0]
    run(fn(*a, **k))
    assert deps.ocr.calls == ocr_calls  # OCR 다시 안 부름
    assert deps.repo.doc.status == DocumentStatus.OCR_DONE
    assert deps.repo.doc.doc_type == DocType.PILL_ENVELOPE
    assert "홍길동" not in json.dumps(deps.repo.lines, ensure_ascii=False)  # 저장된 줄도 가린 값


# ---------------------------------------------------------------------------
# PATCH 고친 값
# ---------------------------------------------------------------------------
def test_edit_marks_user_fields():
    r = edit({"prescribed_date": "2026-11-19", "drugs": [{"line_no": 1, "times_per_day": 2}]})
    assert r["edited"] is True
    assert r["prescribed_date"] == {"value": "2026-11-19", "confidence": None, "needs_check": False}
    d = r["drugs"][0]
    assert d["times_per_day"] == {"value": 2, "confidence": None, "needs_check": False}
    assert len(d["dosage"]["doses"]) == 2  # 횟수에 맞춰 회차 다시 만듦


def test_edit_dose_text_reparsed():
    d = edit({"drugs": [{"line_no": 2, "dose_per_time": {"text": "1/2정"}}]})["drugs"][1]
    assert (d["dose_per_time"]["min"], d["dose_per_time"]["unit"], d["dose_per_time"]["needs_check"]) == (
        0.5,
        "정",
        False,
    )


def test_edit_dose_marks_edited():
    # 고친 용량은 edited: true. 읽을 수 있으면 needs_check: false (명세서 6-2)
    d = edit({"drugs": [{"line_no": 2, "dose_per_time": {"text": "1/2정"}}]})["drugs"][1]
    assert d["dose_per_time"]["edited"] is True and d["dose_per_time"]["needs_check"] is False


def test_edit_dose_unparsed_keeps_needs_check():
    # 6-2 예외: 고친 용량을 읽을 수 없으면(parsed: false) needs_check: true 유지
    d = edit({"drugs": [{"line_no": 2, "dose_per_time": {"text": "적당량"}}]})["drugs"][1]
    dose = d["dose_per_time"]
    assert (dose["parsed"], dose["needs_check"], dose["edited"], dose["confidence"]) == (False, True, True, None)


def test_ocr_dose_not_edited():
    # 고치지 않은 줄의 용량은 edited: false
    d = edit({"drugs": [{"line_no": 2, "times_per_day": 2}]})["drugs"][0]
    assert d["dose_per_time"].get("edited", False) is False


def test_edit_dosage_sets_user():
    d = edit(
        {
            "drugs": [
                {
                    "line_no": 2,
                    "dosage": {
                        "as_needed": False,
                        "doses": [
                            {"dose_no": 1, "meal": "breakfast", "timing": "after_meal", "offset_min": 30},
                            {"dose_no": 2, "meal": "dinner", "timing": "after_meal", "offset_min": 30},
                        ],
                    },
                }
            ]
        }
    )["drugs"][1]
    assert d["dosage"]["parsed_by"] == "user" and d["dosage"]["needs_confirm"] is False


def test_edit_drug_id_and_new_and_delete():
    r = edit(
        {
            "drugs": [
                {"line_no": 2, "drug_id": 2210},
                {"line_no": 1, "deleted": True},
                {
                    "drug_name": "가상시럽",
                    "drug_id": None,
                    "dose_per_time": {"text": "5mL"},
                    "times_per_day": 3,
                    "total_days": 3,
                },
            ]
        }
    )
    assert [d["line_no"] for d in r["drugs"]] == [2, 3]
    assert r["drugs"][0]["match"] == {"status": "exact", "drug_id": 2210, "candidates": []}
    new = r["drugs"][1]
    assert new["page_no"] is None and new["raw_text"] is None
    assert new["dose_per_time"]["unit"] == "mL"


@pytest.mark.parametrize(
    "body, path",
    [
        ({"drugs": [{"line_no": 99, "times_per_day": 1}]}, "drugs[0].line_no"),
        ({"drugs": [{"line_no": 1, "drug_id": 5555}]}, "drugs[0].drug_id"),
        (
            {
                "drugs": [
                    {
                        "line_no": 1,
                        "dosage": {
                            "doses": [{"dose_no": 1, "meal": None, "timing": "between_meals", "offset_min": None}]
                        },
                    }
                ]
            },
            "drugs[0].dosage.doses[0].timing",
        ),
    ],
)
def test_edit_validation_errors(body, path):
    with pytest.raises(sp.ScanValidationError) as e:
        edit(body)
    assert path in e.value.fields


# ---------------------------------------------------------------------------
# 확정·취소·정리
# ---------------------------------------------------------------------------
def test_confirm_deletes_files_after_commit_even_if_delete_fails():
    deps = make_deps(files=FakeFiles(fail=True))
    run(sp.run_scan_job(deps, 42))
    from app.dtos.scan import ConfirmRequest

    body = ConfirmRequest.model_validate(
        json.loads((Path(__file__).parent / "fixtures" / "scan_examples.json").read_text(encoding="utf-8"))[
            "confirm_request"
        ]
    )
    calls = []

    async def fake_create(conn, user_id, data, **kw):
        calls.append((conn, kw["source"]))
        return {"prescription_id": 88, "conditions_to_confirm": []}

    resp = run(sp.confirm_scan(deps, 42, 7, body, fake_create))
    assert resp["prescription_id"] == 88 and calls == [("conn", "ocr")]  # 트랜잭션 연결을 넘김
    assert deps.repo.doc.pages_left is True  # 삭제 실패 → 정리 작업 몫


def test_cancel_is_idempotent():
    deps = make_deps()
    run(sp.cancel_scan(deps, 42, 7))
    assert deps.repo.doc.status == DocumentStatus.EXPIRED and deps.files.deleted == [42]
    run(sp.cancel_scan(deps, 42, 7))
    assert deps.files.deleted == [42]


def test_cleanup_selection():
    docs = [
        new_doc(scan_id=1, status=DocumentStatus.OCR_DONE, image_delete_due_at=NOW - timedelta(minutes=1)),
        new_doc(scan_id=2, status=DocumentStatus.OCR_DONE),
        new_doc(scan_id=3, status=DocumentStatus.CONFIRMED, pages_left=True),
        new_doc(scan_id=4, status=DocumentStatus.EXPIRED, pages_left=False),
    ]
    acts = {a.scan_id: a for a in sp.select_cleanup_actions(docs, NOW)}
    assert set(acts) == {1, 3}
    assert acts[1].expire is True and acts[3].expire is False


def test_confirm_rejects_not_ready_and_other_user():
    deps = make_deps()  # 아직 uploaded
    from app.dtos.scan import ConfirmRequest

    body = ConfirmRequest.model_validate(
        json.loads((Path(__file__).parent / "fixtures" / "scan_examples.json").read_text(encoding="utf-8"))[
            "confirm_request"
        ]
    )

    async def never(*a, **k):
        raise AssertionError("부르면 안 됨")

    with pytest.raises(sp.ScanStateError) as e:
        run(sp.confirm_scan(deps, 42, 7, body, never))
    assert e.value.code == "DOCUMENT_NOT_READY"
    with pytest.raises(sp.ScanStateError) as e:
        run(sp.confirm_scan(deps, 42, 999, body, never))
    assert e.value.code == "NOT_FOUND"


def test_ocr_call_timeout_counts_as_failure():
    class Slow(FakeOcr):
        async def read_page(self, image):
            await asyncio.sleep(1)

    sp_timeout, sp.OCR_TIMEOUT_SEC = sp.OCR_TIMEOUT_SEC, 0.01
    try:
        assert_reason(make_deps(ocr=Slow()), FailReason.OCR_ERROR)
    finally:
        sp.OCR_TIMEOUT_SEC = sp_timeout


def test_drug_matching_runs_concurrently():
    class CountingCatalog(FakeCatalog):
        running = peak = 0

        async def match(self, name):
            CountingCatalog.running += 1
            CountingCatalog.peak = max(CountingCatalog.peak, CountingCatalog.running)
            await asyncio.sleep(0.01)
            CountingCatalog.running -= 1
            return await super().match(name)

    deps = make_deps()
    deps.catalog = CountingCatalog()
    run(sp.run_scan_job(deps, 42))
    assert deps.repo.doc.status == DocumentStatus.OCR_DONE
    assert CountingCatalog.peak == 2  # 약 2개를 동시에 매칭


def test_cleanup_skips_doc_confirmed_in_between():
    deps = make_deps(doc=new_doc(status=DocumentStatus.OCR_DONE, image_delete_due_at=NOW - timedelta(minutes=1)))
    stale = deps.repo.doc
    deps.repo.doc = replace(stale, status=DocumentStatus.CONFIRMED)  # 목록을 뽑은 뒤 확정됨
    run(sp.run_cleanup(deps, [stale]))
    assert deps.repo.doc.status == DocumentStatus.CONFIRMED


def test_mask_lines_phone_split_over_two_lines():
    # 실제 CLOVA 응답 case12: '연락처: 010-' / '0000-0000' 이 두 줄로 나뉨
    lines = [
        sp.make_line(
            1,
            4,
            [W("주민등록번호:", 0.99), W("000101-3000000", 0.99), W("|", 0.99), W("연락처:", 0.99), W("010-", 0.99)],
        ),
        sp.make_line(1, 5, [W("0000-0000", 1.0)]),
        sp.make_line(1, 6, [W("의약품명", 0.99)]),
    ]
    masked = sp.mask_lines(lines)
    assert masked[0].text == "주민등록번호: [주민번호] | 연락처: [연락처]"
    assert masked[1].text == ""
    assert masked[2].text == "의약품명"
    assert [ln.line_idx for ln in masked] == [4, 5, 6]


def test_mask_lines_same_as_mask_line_when_not_split():
    lines = [
        sp.make_line(1, 0, [W("TEL:", 0.99), W("053-123-4567", 0.99)]),
        sp.make_line(1, 1, [W("세토펜정", 0.99), W("1정", 0.99), W("3회", 0.99), W("3일", 0.99)]),
    ]
    assert [ln.text for ln in sp.mask_lines(lines)] == [sp.mask_line(ln).text for ln in lines]
