"""_retry 실패 로그: 원인 종류 이름은 남기고, 에러 메시지(처방 내용이 섞일 수 있음)는 남기지 않음."""

import asyncio
import logging

import pytest
from pydantic import ValidationError

import app.services.scan_service as sp
from app.dtos.scan import FailReason


def test_retry_failure_logs_error_type_without_content(caplog):
    async def bad_llm():
        # LLM이 형식이 틀린 응답을 줌 → 검증 에러 메시지에 응답 내용(약 이름)이 들어 있음
        return sp.LlmDrug.model_validate({"line_ref": "p1-l0", "drug_name": "가상정비밀약", "times_per_day": "세번"})

    with caplog.at_level(logging.WARNING, logger=sp.__name__):
        with pytest.raises(sp.ScanFailed) as e:
            asyncio.run(sp._retry(bad_llm, retries=1, fail=FailReason.STRUCTURE_ERROR))

    assert e.value.reason == FailReason.STRUCTURE_ERROR
    assert e.value.__cause__ is None and e.value.__suppress_context__ is True  # from None
    assert "reason=structure_error" in caplog.text
    assert f"error={ValidationError.__name__}" in caplog.text
    assert "가상정비밀약" not in caplog.text and "세번" not in caplog.text
    assert len(caplog.records) == 1  # 마지막 실패에서만 남김


def test_retry_success_logs_nothing(caplog):
    calls = []

    async def flaky():
        calls.append(1)
        if len(calls) == 1:
            raise TimeoutError
        return "ok"

    with caplog.at_level(logging.WARNING, logger=sp.__name__):
        assert asyncio.run(sp._retry(flaky, retries=2, fail=FailReason.OCR_ERROR)) == "ok"
    assert caplog.records == []
