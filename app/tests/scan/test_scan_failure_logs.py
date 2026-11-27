"""실패 로그: 에러 종류 이름과 문서 번호만 남기고, 에러 메시지(처방·OCR 글자가 섞일 수 있음)는 남기지 않음.

_retry 로그는 test_scan_retry_log.py에 있어요.
"""

import logging
import subprocess
import sys
from pathlib import Path

import app.services.scan_service as sp
from app.dtos.scan import DocumentStatus, DrugMatch, FailReason, MatchStatus
from app.tests.scan.fakes import NOW, FakeFiles, make_deps, run

SECRET = "가상정비밀약"  # 로그에 나오면 안 되는 글자


class BrokenCatalog:
    async def match(self, name):
        raise RuntimeError(f"{SECRET} 매칭 중 에러")

    async def get_many(self, drug_ids):
        return {}


class BrokenParser:
    def parse(self, text, times, start):
        raise ValueError(f"{SECRET} 해석 실패")


def test_unexpected_error_in_job_logs_type_and_scan_id(caplog):
    deps = make_deps()
    deps.catalog = BrokenCatalog()  # 재시도 밖(④ 줄별 처리)에서 예상 못 한 에러
    with caplog.at_level(logging.WARNING, logger=sp.__name__):
        run(sp.run_scan_job(deps, 42))

    assert deps.repo.doc.status == DocumentStatus.OCR_FAILED
    assert deps.repo.doc.fail_reason == FailReason.OCR_ERROR
    assert "scan job failed: scan_id=42 error=RuntimeError" in caplog.text
    (rec,) = [r for r in caplog.records if "scan job failed" in r.getMessage()]
    assert rec.levelno == logging.ERROR  # 예상 못 한 에러는 error, 나머지(사전·사진 삭제)는 warning
    assert SECRET not in caplog.text
    assert all(r.exc_info is None for r in caplog.records)  # 스택(logger.exception) 안 남김


def test_instruction_parse_failure_logs_type(caplog):
    llm = sp.LlmDrug(line_ref="p1-l0", drug_name="가상정", dose_text="1정", times_per_day=2, instruction_text="식후")
    match = DrugMatch(status=MatchStatus.NONE, drug_id=None, candidates=[])
    with caplog.at_level(logging.WARNING, logger=sp.__name__):
        d = sp.build_scan_drug(
            llm, None, 1, start_date=NOW.date(), match=match, is_oral=True, instructions=BrokenParser()
        )
    assert d.dosage.needs_confirm is True  # 사전 대신 기본값(확인 필요)
    assert "instruction parse failed, fallback used: error=ValueError" in caplog.text
    assert all(r.levelno == logging.WARNING for r in caplog.records)
    assert SECRET not in caplog.text


def test_page_delete_failure_logs_type(caplog):
    deps = make_deps(files=FakeFiles(fail=True))
    with caplog.at_level(logging.WARNING, logger=sp.__name__):
        run(sp._delete_files_quietly(deps, 42))
    assert "page file delete failed: scan_id=42 error=OSError" in caplog.text


def test_importing_clova_ocr_does_not_read_app_config():
    # 다른 테스트가 이미 app.core를 불러왔을 수 있어 새 프로세스에서 확인
    root = Path(__file__).resolve().parents[3]
    code = "import sys, app.services.clova_ocr; print('app.core' in sys.modules)"
    out = subprocess.run([sys.executable, "-c", code], cwd=root, capture_output=True, text=True, check=True)
    assert out.stdout.strip() == "False"
