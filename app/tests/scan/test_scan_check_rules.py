"""인식 결과 확인 표시 규칙 (명세서 6-2).

- 먹는 약이 아닌 줄(is_oral: false)은 확정 때 빠지므로 복용 조건 확인(needs_confirm)을 요구하지 않음
- 정·캡슐·포인데 1회 용량이 0.25 미만이면 OCR이 숫자를 잘못 읽었을 수 있어 needs_check를 켬
"""

import pytest

import app.services.scan_service as sp
from app.dtos.scan import DrugMatch, MatchStatus, ScanEditRequest
from app.services.text_rules import is_suspicious_dose, parse_dose_text
from app.tests.scan.fakes import NOW, FakeCatalog, FakeInstructions, parsed_after_job, run


def apply(body: dict, base: dict) -> dict:
    req = ScanEditRequest.model_validate(body)
    lookup = run(sp.lookup_edit_drugs(FakeCatalog(), req))
    return sp.apply_edits(base, req, drug_lookup=lookup, instructions=FakeInstructions(), today=NOW.date())


def scan_drug(*, dose_text: str = "1정", is_oral: bool | None = True) -> sp.ScanDrug:
    llm = sp.LlmDrug(
        line_ref="p1-l0",
        drug_name="가상정",
        dose_text=dose_text,
        times_per_day=2,
        total_days=7,
        instruction_text="환부에 바름",
    )
    match = DrugMatch(status=MatchStatus.EXACT, drug_id=9, candidates=[])
    # OCR 줄이 있어야 원문 신뢰도로 칸을 만듦(줄이 없으면 '정리하면서 바뀐 칸'이라 항상 needs_check)
    words = [sp.OcrWord(t, 0.99) for t in ("가상정", dose_text, "2", "7", "환부에", "바름")]
    line = sp.make_line(1, 0, words)
    return sp.build_scan_drug(
        llm, line, 1, start_date=NOW.date(), match=match, is_oral=is_oral, instructions=FakeInstructions()
    )


# ---------------------------------------------------------------------------
# is_oral: false → needs_confirm: false
# ---------------------------------------------------------------------------
def test_non_oral_line_does_not_need_confirm():
    assert scan_drug(is_oral=False).dosage.needs_confirm is False


@pytest.mark.parametrize("is_oral", [True, None])
def test_oral_or_unknown_line_still_needs_confirm(is_oral):
    # '환부에 바름'은 사전에 없음 → 먹는 약이거나 모르면 확인 필요 그대로
    assert scan_drug(is_oral=is_oral).dosage.needs_confirm is True


def test_edit_to_non_oral_and_back_updates_needs_confirm():
    parsed = parsed_after_job()
    assert parsed["drugs"][1]["dosage"]["needs_confirm"] is True

    to_ointment = apply({"drugs": [{"line_no": 2, "drug_id": 9}]}, parsed)  # FakeCatalog 9 = 가상연고
    assert to_ointment["drugs"][1]["is_oral"] is False
    assert to_ointment["drugs"][1]["dosage"]["needs_confirm"] is False

    back = apply({"drugs": [{"line_no": 2, "drug_id": 2210}]}, to_ointment)
    assert back["drugs"][1]["is_oral"] is True
    assert back["drugs"][1]["dosage"]["needs_confirm"] is True


# ---------------------------------------------------------------------------
# 정·캡슐·포 0.25 미만 → needs_check: true
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "text, suspicious",
    [
        ("0.1정", True),
        ("0.2캡슐", True),
        ("0.1포", True),
        ("1/8정", True),
        ("0.1~1정", True),  # 범위면 작은 쪽 기준
        ("1/4정", False),  # 0.25는 경계값이라 정상
        ("0.5정", False),
        ("1정", False),
        ("0.1mL", False),  # 정·캡슐·포가 아님
        ("0.1g", False),
        ("적당량", False),  # 못 읽은 용량은 parsed: false로 이미 needs_check
    ],
)
def test_is_suspicious_dose(text, suspicious):
    assert is_suspicious_dose(parse_dose_text(text)) is suspicious


def test_small_ocr_dose_needs_check():
    assert scan_drug(dose_text="0.1정").dose_per_time.needs_check is True
    assert scan_drug(dose_text="1/2정").dose_per_time.needs_check is False


def test_small_edited_dose_needs_check():
    # 회원이 고친 용량도 0.25 미만이면 노란색 유지(확정은 막지 않음)
    r = apply({"drugs": [{"line_no": 1, "dose_per_time": {"text": "0.1정"}}]}, parsed_after_job())
    assert r["drugs"][0]["dose_per_time"]["needs_check"] is True
    r = apply({"drugs": [{"line_no": 1, "dose_per_time": {"text": "1/2정"}}]}, parsed_after_job())
    assert r["drugs"][0]["dose_per_time"]["needs_check"] is False
