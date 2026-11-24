"""명세서 6장 예시(fixtures/scan_examples.json)가 v1 모델과 맞는지 확인합니다.
명세서 예시를 고치면 examples 파일도 같이 고쳐 주세요."""
import json
from pathlib import Path

import pytest
from pydantic import TypeAdapter, ValidationError

import app.dtos.scan as c

EXAMPLES = json.loads((Path(__file__).parent / "fixtures" / "scan_examples.json").read_text(encoding="utf-8"))
STATUS = TypeAdapter(c.ScanStatusResponse)

CASES = {
    "post_scans_202": c.ScanCreatedResponse,
    "get_scan_uploaded": STATUS,
    "get_scan_ocr_done": STATUS,
    "get_scan_ocr_failed": STATUS,
    "get_scan_confirmed": STATUS,
    "get_scan_expired": STATUS,
    "patch_scan_edit_request": c.ScanEditRequest,
    "patch_scan_doc_type_request": c.ScanDocTypeRequest,
    "patch_scan_doc_type_202": c.ScanDocTypeResponse,
    "confirm_request": c.ConfirmRequest,
    "confirm_201": c.ConfirmResponse,
    "validation_error": c.ErrorResponse,
}


def _validate(model, data):
    return model.validate_python(data) if isinstance(model, TypeAdapter) else model.model_validate(data)


@pytest.mark.parametrize("name", CASES)
def test_spec_examples_fit(name):
    _validate(CASES[name], EXAMPLES[name])


def test_status_union_picks_right_model():
    assert isinstance(_validate(STATUS, EXAMPLES["get_scan_ocr_done"]), c.ScanOcrDoneResponse)
    assert isinstance(_validate(STATUS, EXAMPLES["get_scan_ocr_failed"]), c.ScanOcrFailedResponse)


def test_fail_message_matches_table():
    failed = EXAMPLES["get_scan_ocr_failed"]
    assert c.FAIL_MESSAGES[c.FailReason(failed["fail_reason"])] == failed["message"]


def test_candidates_max_three():
    data = json.loads(json.dumps(EXAMPLES["get_scan_ocr_done"]))
    cand = data["drugs"][1]["match"]["candidates"][0]
    data["drugs"][1]["match"]["candidates"] = [cand] * 4
    with pytest.raises(ValidationError):
        _validate(STATUS, data)


def test_unknown_status_rejected():
    with pytest.raises(ValidationError):
        _validate(STATUS, {"scan_id": 1, "status": "DRAFT", "step": None})
