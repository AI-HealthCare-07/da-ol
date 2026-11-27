"""scan 테스트에서 같이 쓰는 가짜 외부 연결(OCR·LLM·약품 DB·저장소)과 도우미 함수."""

import asyncio
import json
from contextlib import asynccontextmanager
from dataclasses import replace
from datetime import datetime, timedelta

import app.services.scan_service as sp
from app.dtos.scan import (
    Cycle,
    CycleType,
    DocType,
    DocumentStatus,
    Dosage,
    Dose,
    DrugMatch,
    MatchStatus,
    Meal,
    ParsedBy,
    ScanEditRequest,
    ScanStep,
    Timing,
)

NOW = datetime(2026, 11, 20, 18, 30)
W = sp.OcrWord


def run(coro):
    return asyncio.run(coro)


# ---------------------------------------------------------------------------
# 가짜 외부 연결
# ---------------------------------------------------------------------------
def page1_lines():
    return [
        sp.make_line(0, 0, [W("가상내과의원", 0.97)]),
        sp.make_line(0, 1, [W("성명", 0.99), W("홍길동", 0.95), W("주민등록번호", 0.98), W("900101-1234567", 0.96)]),
        sp.make_line(0, 2, [W("교부일", 0.9), W("2026.11.20", 0.93)]),
        sp.make_line(0, 3, [W("가상정5mg", 0.91), W("1정", 0.95), W("3", 0.72), W("5", 0.94), W("식후30분", 0.9)]),
        sp.make_line(0, 4, [W("가상캡슐", 0.84), W("1캡슐", 0.9), W("2", 0.88), W("5", 0.9)]),
    ]


class FakeOcr:
    def __init__(self, fail_times=0):
        self.fail_times, self.calls = fail_times, 0

    async def read_page(self, image):
        self.calls += 1
        if self.calls <= self.fail_times:
            raise TimeoutError
        return page1_lines()


GOOD_LLM = {
    "hospital_name": "가상내과의원",
    "prescribed_date": "2026-11-20",
    "drugs": [
        {"line_ref": "p1-l4", "drug_name": "가상캡슐", "dose_text": "1캡슐", "times_per_day": 2, "total_days": 5},
        {
            "line_ref": "p1-l3",
            "drug_name": "가상정5mg",
            "dose_text": "1정",
            "times_per_day": 3,
            "total_days": 5,
            "instruction_text": "식후30분",
        },
    ],
}


class FakeLlm:
    def __init__(self, responses):
        self.responses, self.seen = list(responses), []

    async def structure(self, numbered_lines, doc_type):
        self.seen.append(numbered_lines)
        r = self.responses.pop(0)
        return r if isinstance(r, str) else json.dumps(r, ensure_ascii=False)


class FakeCatalog:
    DB = {1203: ("가상정 5mg", True), 2210: ("가상캡슐 250mg", True), 9: ("가상연고", False)}

    async def match(self, name):
        if name == "가상정5mg":
            return DrugMatch(status=MatchStatus.EXACT, drug_id=1203, candidates=[]), True
        return DrugMatch(status=MatchStatus.NONE, drug_id=None, candidates=[]), None

    async def get_many(self, drug_ids):
        return {i: self.DB[i] for i in drug_ids if i in self.DB}


class FakeInstructions:
    def parse(self, text, times, start):
        if text == "식후30분" and times:
            meals = [Meal.BREAKFAST, Meal.LUNCH, Meal.DINNER]
            return Dosage(
                parsed_by=ParsedBy.RULE,
                needs_confirm=False,
                as_needed=False,
                doses=[
                    Dose(dose_no=i + 1, meal=meals[i] if times == 3 else None, timing=Timing.AFTER_MEAL, offset_min=30)
                    for i in range(times)
                ],
                cycle=Cycle(type=CycleType.DAILY, start_date=start),
            )
        return sp.fallback_dosage(times, start)


class FakeFiles:
    def __init__(self, fail=False):
        self.fail, self.deleted = fail, []

    async def delete_pages(self, scan_id):
        if self.fail:
            raise OSError
        self.deleted.append(scan_id)


class FakeRepo:
    def __init__(self, doc):
        self.doc, self.lines, self.pages_deleted_at = doc, None, None
        self.tx_count = 0
        self.expire_after_reads = None  # n번째 get 뒤에 취소된 것처럼

    @asynccontextmanager
    async def transaction(self):
        self.tx_count += 1
        yield "conn"

    async def get(self, scan_id, *, for_update=False, conn=None):
        if self.expire_after_reads is not None:
            self.expire_after_reads -= 1
            if self.expire_after_reads < 0:
                self.doc = replace(self.doc, status=DocumentStatus.EXPIRED)
        return self.doc

    async def set_step(self, scan_id, step):
        self.doc = replace(self.doc, step=step)

    async def set_reprocessing(self, scan_id, doc_type, now, *, conn=None):
        self.doc = replace(
            self.doc,
            status=DocumentStatus.UPLOADED,
            step=ScanStep.STRUCTURING,
            doc_type=doc_type,
            processing_started_at=now,
            parsed_result=None,
            fail_reason=None,
        )

    async def finish_ocr_done(self, scan_id, parsed):
        self.doc = replace(self.doc, status=DocumentStatus.OCR_DONE, step=None, parsed_result=parsed)
        return True

    async def finish_ocr_failed(self, scan_id, reason):
        self.doc = replace(self.doc, status=DocumentStatus.OCR_FAILED, step=None, fail_reason=reason)
        return True

    async def save_parsed_result(self, scan_id, parsed):
        self.doc = replace(self.doc, parsed_result=parsed)

    async def expire(self, scan_id, *, conn=None):
        self.doc = replace(self.doc, status=DocumentStatus.EXPIRED, parsed_result=None)

    async def page_images(self, scan_id):
        return [(1, b"img")]

    async def save_masked_lines(self, scan_id, lines):
        self.lines = lines

    async def load_masked_lines(self, scan_id):
        return self.lines

    async def mark_pages_deleted(self, scan_id, now):
        self.pages_deleted_at = now
        self.doc = replace(self.doc, pages_left=False)


def new_doc(**kw):
    base = dict(
        scan_id=42,
        user_id=7,
        status=DocumentStatus.UPLOADED,
        step=ScanStep.READING,
        doc_type=DocType.PRESCRIPTION,
        processing_started_at=NOW - timedelta(seconds=5),
        image_delete_due_at=NOW + timedelta(hours=3),
        page_count=1,
    )
    base.update(kw)
    return sp.ScanDoc(**base)


def make_deps(llm_responses=(GOOD_LLM,), ocr=None, doc=None, files=None):
    return sp.Deps(
        repo=FakeRepo(doc or new_doc()),
        ocr=ocr or FakeOcr(),
        llm=FakeLlm(llm_responses),
        catalog=FakeCatalog(),
        instructions=FakeInstructions(),
        files=files or FakeFiles(),
        now=lambda: NOW,
    )


def fill_meals_passthrough(doses, times):
    return doses


def parsed_after_job():
    deps = make_deps()
    run(sp.run_scan_job(deps, 42))
    return deps.repo.doc.parsed_result


def edit(body):
    req = ScanEditRequest.model_validate(body)
    lookup = run(sp.lookup_edit_drugs(FakeCatalog(), req))
    return sp.apply_edits(
        parsed_after_job(), req, drug_lookup=lookup, instructions=FakeInstructions(), today=NOW.date()
    )
