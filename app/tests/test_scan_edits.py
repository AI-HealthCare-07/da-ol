"""PATCH /scans 고친 값 저장 규칙 (6장, 11/26 설아님과 정함).

- 프론트는 안 바꾼 칸을 빼고 보내고 null은 보내지 않음 → dose_per_time·dosage에 null이 오면 422
- 1회 용량 칸을 비우면 {"text": ""} → 읽을 수 없는 용량과 같게(parsed: false, needs_check: true, edited: true)
"""

import asyncio

import pytest

import app.services.scan_service as sp
from app.dtos.scan import ScanEditRequest, ScanStep
from app.tests.test_scan_service import (
    NOW,
    FakeCatalog,
    FakeInstructions,
    edit,
    fill_meals_passthrough,
    make_deps,
    new_doc,
    parsed_after_job,
)


@pytest.mark.parametrize("field", ["dose_per_time", "dosage"])
def test_null_is_validation_error(field):
    with pytest.raises(sp.ScanValidationError) as e:
        edit({"drugs": [{"line_no": 1, "total_days": 5}, {"line_no": 2, field: None}]})
    assert list(e.value.fields) == [f"drugs[1].{field}"]  # 어느 줄·칸인지


def test_null_in_both_fields_reports_both():
    with pytest.raises(sp.ScanValidationError) as e:
        edit({"drugs": [{"line_no": 1, "dose_per_time": None, "dosage": None}]})
    assert set(e.value.fields) == {"drugs[0].dose_per_time", "drugs[0].dosage"}


def test_null_rejects_whole_request():
    # 한 줄이라도 잘못되면 아무것도 저장하지 않음(다른 줄의 total_days도 반영 안 됨)
    parsed = parsed_after_job()
    req = ScanEditRequest.model_validate({"drugs": [{"line_no": 1, "total_days": 99}, {"line_no": 2, "dosage": None}]})
    lookup = asyncio.run(sp.lookup_edit_drugs(FakeCatalog(), req))
    with pytest.raises(sp.ScanValidationError):
        sp.apply_edits(parsed, req, drug_lookup=lookup, instructions=FakeInstructions(), today=NOW.date())
    assert parsed["drugs"][0]["total_days"]["value"] != 99


def test_empty_dose_text_is_unreadable_dose():
    d = edit({"drugs": [{"line_no": 1, "dose_per_time": {"text": ""}}]})["drugs"][0]["dose_per_time"]
    assert d["text"] == "" and d["parsed"] is False
    assert d["min"] is None and d["max"] is None and d["unit"] is None
    assert d["needs_check"] is True and d["edited"] is True and d["confidence"] is None


def test_null_still_allowed_where_it_means_something():
    # drug_id: null = 약 매칭 해제, times_per_day: null = 필요시 약처럼 횟수 비우기 (기존 동작 유지)
    r = edit({"drugs": [{"line_no": 1, "drug_id": None, "times_per_day": None}]})["drugs"][0]
    assert r["match"]["status"] == "none" and r["is_oral"] is None
    assert r["times_per_day"]["value"] is None


def test_uploaded_without_step_shows_reading():
    deps = make_deps(doc=new_doc(step=None))  # 업로드 직후 작업이 아직 step을 못 채움
    resp = asyncio.run(sp.get_scan(deps, 42, fill_default_meals=fill_meals_passthrough))
    assert resp.step == ScanStep.READING
