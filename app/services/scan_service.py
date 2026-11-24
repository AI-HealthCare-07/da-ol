"""
처방 등록 OCR 파이프라인 v2 (비동기) — 담당: AI A 채민
기준: API 명세서 6장, 계약 app/dtos/scan.py(v1.1), 공용 함수 app/services/text_rules.py(6-4)

구성
- 순수 함수(동기, 테스트 있음): mask_line, build_field, build_scan_drug, apply_edits,
  can_repick_doc_type, is_timed_out, select_cleanup_actions
- 오케스트레이션(async): run_scan_job, assemble_parsed_result, get_scan, lookup_edit_drugs,
  repick_doc_type, confirm_scan, cancel_scan, run_cleanup
- 외부 연결(async, 백엔드 코드에 맞춰 구현): ScanRepo(Tortoise), OcrClient(CLOVA), Structurer(LLM),
  DrugCatalog(pg_trgm), FileStore. InstructionParser(표현 사전)는 메모리 안에서 끝나므로 동기.

트랜잭션
- 상태를 바꿀 때마다 저장소 메서드 하나가 짧은 트랜잭션으로 끝납니다. CLOVA·LLM을 기다리는 동안
  문서 행을 잠그지 않아야 그사이 들어온 취소(DELETE)가 막히지 않기 때문입니다.
- 확정·취소·다시 고르기처럼 "잠그고 확인 후 바꾸기"는 repo.transaction() 안에서 conn을 넘겨 처리하고,
  파일 삭제는 블록을 나온 뒤(커밋 후)에 합니다.
- PDF 렌더링 같은 무거운 동기 작업을 async 함수 안에서 할 때는 asyncio.to_thread()로 감쌉니다.
"""
from __future__ import annotations

import asyncio
import re
from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass, replace
from datetime import date, datetime, timedelta
from typing import Any, Awaitable, Callable, Protocol

from pydantic import BaseModel

from app.services.text_rules import apply_mask_spans, find_mask_spans, parse_dose_text
from app.dtos.scan import (
    CONFIRM_ALLOWED_TIMINGS, DOC_TYPE_RETRY_REASONS, FAIL_MESSAGES,
    ConfirmRequest, Cycle, CycleType, DocType, DocumentStatus, Dosage, DosePerTimeField,
    DrugMatch, FailReason, FieldValue, MatchStatus, ParsedBy, ScanConfirmedResponse,
    ScanDrug, ScanEditRequest, ScanExpiredResponse, ScanOcrDoneResponse,
    ScanOcrFailedResponse, ScanPage, ScanStep, ScanUploadedResponse, Dose,
)

# ---------------------------------------------------------------------------
# 명세서 수치 (테스트 후 조정)
# ---------------------------------------------------------------------------
IMAGE_TTL = timedelta(hours=3)          # image_delete_due_at
JOB_TIMEOUT = timedelta(seconds=90)     # ocr_failed(timeout)
OCR_TIMEOUT_SEC = 10                    # 페이지당
OCR_MAX_RETRY = 2
LLM_MAX_RETRY = 1
NEEDS_CHECK_BELOW = 0.8
MAX_FILE_BYTES = 10 * 1024 * 1024
MAX_TOTAL_BYTES = 30 * 1024 * 1024
MAX_PAGES = 10
DAILY_SCAN_LIMIT = 20                   # expired 문서도 셈
PROMPT_VERSION = "parse_document_v1"


class ScanFailed(Exception):
    def __init__(self, reason: FailReason):
        super().__init__(reason.value)
        self.reason = reason


class ScanCancelled(Exception):
    """DELETE /scans로 expired가 됨 → 결과를 버리고 끝냄."""


class ScanValidationError(Exception):
    """VALIDATION_ERROR(422). fields = {"drugs[1].line_no": "사유 문장"}"""
    def __init__(self, fields: dict[str, str]):
        super().__init__("VALIDATION_ERROR")
        self.fields = fields


# ---------------------------------------------------------------------------
# OCR 결과 모양 (메모리 안에서만 쓰고, 가리기 전 글자는 저장·로그·LLM으로 보내지 않음)
# ---------------------------------------------------------------------------
@dataclass
class OcrWord:
    text: str
    confidence: float
    start: int = 0          # 줄 글자 안의 위치
    end: int = 0


@dataclass
class OcrLine:
    page_no: int
    line_idx: int           # 페이지 안 줄 순서(0부터)
    words: list[OcrWord]
    text: str = ""

    @property
    def ref(self) -> str:   # LLM에 넘기는 줄 번호
        return f"p{self.page_no}-l{self.line_idx}"


def make_line(page_no: int, line_idx: int, words: list[OcrWord]) -> OcrLine:
    """단어를 공백 하나로 이어 줄 글자를 만들고 단어 위치를 기록합니다."""
    pos, placed = 0, []
    for w in words:
        if not w.text:
            continue
        placed.append(replace(w, start=pos, end=pos + len(w.text)))
        pos += len(w.text) + 1
    return OcrLine(page_no, line_idx, placed, " ".join(w.text for w in placed))


def mask_line(line: OcrLine) -> OcrLine:
    """② 줄 단위로 가립니다. '성명'과 이름이 다른 단어여도 같은 줄이면 잡힙니다.
    여러 단어에 걸친 구간은 첫 단어에 토큰을 두고 나머지 단어에서는 그 부분을 지웁니다.
    단어 신뢰도는 그대로 둡니다(6-2 칸 신뢰도 계산용)."""
    spans = find_mask_spans(line.text)
    if not spans:
        return line
    used: set[int] = set()
    new_words = []
    for w in line.words:
        local = []
        for i, (s, e, token) in enumerate(spans):
            if e <= w.start or s >= w.end:
                continue
            cs, ce = max(s, w.start) - w.start, min(e, w.end) - w.start
            local.append((cs, ce, "" if i in used else token))
            used.add(i)
        new_words.append(replace(w, text=apply_mask_spans(w.text, local)) if local else w)
    return make_line(line.page_no, line.line_idx, new_words)


# ---------------------------------------------------------------------------
# 외부 연결
# ---------------------------------------------------------------------------
class OcrClient(Protocol):
    async def read_page(self, image: bytes) -> list[OcrLine]:
        """CLOVA General OCR(V2, ko, enableTableDetection). 표가 있으면 표의 한 행을 한 줄로,
        없으면 lineBreak·boundingPoly y좌표로 묶어 make_line()으로 만든 줄 목록.
        httpx.AsyncClient 사용. 실패 시 예외(재시도·10초 제한은 호출하는 쪽)."""


class LlmDrug(BaseModel):
    line_ref: str                       # "p1-l7"
    drug_name: str
    dose_text: str | None = None
    times_per_day: int | None = None
    total_days: int | None = None
    instruction_text: str | None = None


class LlmDocument(BaseModel):
    """parse_document_v1 프롬프트가 돌려줄 JSON. 형식 검사 실패 = 재요청 대상."""
    hospital_name: str | None = None
    prescribed_date: date | None = None
    drugs: list[LlmDrug]


class Structurer(Protocol):
    async def structure(self, numbered_lines: list[str], doc_type: DocType) -> str:
        """LLM 원문 응답(JSON 문자열). llm_call_logs에는 메타 정보만 남기고 본문은 남기지 않음."""


class DrugCatalog(Protocol):
    async def match(self, drug_name: str) -> tuple[DrugMatch, bool | None]:
        """GET /drugs와 같은 검색 함수(item_name_norm 기준 exact → prefix → pg_trgm ≥ 0.3).
        검색어도 normalize_drug_name()으로 정규화. DrugMatch와 is_oral을 돌려줌."""

    async def get_many(self, drug_ids: list[int]) -> dict[int, tuple[str, bool | None]]:
        """{drug_id: (item_name, is_oral)}. 없는 id는 빠짐."""


class InstructionParser(Protocol):
    def parse(self, instruction_text: str | None, times_per_day: int | None,
              start_date: date) -> Dosage:
        """복용 조건 표현 사전(parsed_by=rule). 사전에 없거나 1차 미계산 조건이면 needs_confirm=True."""


class FileStore(Protocol):
    async def delete_pages(self, scan_id: int) -> None: ...


class ScanRepo(Protocol):
    """Tortoise 구현은 app/repositories/scan_repository.py. conn이 있으면 그 트랜잭션 안에서 실행."""
    def transaction(self) -> AbstractAsyncContextManager[Any]: ...          # in_transaction()
    async def get(self, scan_id: int, *, for_update: bool = False, conn: Any = None) -> "ScanDoc": ...
    async def set_step(self, scan_id: int, step: ScanStep) -> None: ...
    async def set_reprocessing(self, scan_id: int, doc_type: DocType, now: datetime, *, conn: Any = None) -> None: ...
    async def finish_ocr_done(self, scan_id: int, parsed_result: dict) -> bool: ...
    async def finish_ocr_failed(self, scan_id: int, reason: FailReason) -> bool: ...
    async def save_parsed_result(self, scan_id: int, parsed_result: dict) -> None: ...
    async def expire(self, scan_id: int, *, conn: Any = None) -> None: ...  # status=expired, parsed_result·masked_lines=NULL
    async def page_images(self, scan_id: int) -> list[tuple[int, bytes]]: ...
    async def save_masked_lines(self, scan_id: int, lines: list[dict]) -> None: ...   # ⚠ 저장 칸 미정
    async def load_masked_lines(self, scan_id: int) -> list[dict]: ...
    async def mark_pages_deleted(self, scan_id: int, now: datetime) -> None: ...


@dataclass
class ScanDoc:
    scan_id: int
    user_id: int
    status: DocumentStatus
    step: ScanStep | None
    doc_type: DocType
    processing_started_at: datetime     # ⚠ 90초 기준. 업로드 시각, 문서 종류 다시 고르면 그 시각
    image_delete_due_at: datetime
    page_count: int
    fail_reason: FailReason | None = None
    parsed_result: dict | None = None
    prescription_id: int | None = None
    pages_left: bool = True             # document_pages.deleted_at이 빈 페이지가 있는지


# ---------------------------------------------------------------------------
# 칸 만들기 (6-2)
# ---------------------------------------------------------------------------
def _norm(s: str) -> str:
    return re.sub(r"\s+", "", s)


def build_field(value, line: OcrLine | None, *, kind: str = "text",
                exclude: tuple[int, int] | None = None) -> FieldValue:
    """원문 단어에서 그대로 온 값이면 그 단어들의 최소 신뢰도, 아니면 confidence=None·needs_check=True.
    kind: "text"(부분 문자열), "int"(같은 숫자 단어, 여러 개면 가장 낮은 신뢰도), "date"(숫자만 비교).
    값이 없으면 needs_check=True."""
    if value is None or line is None:
        return FieldValue(value=value, confidence=None, needs_check=True)

    hits: list[OcrWord] = []
    if kind == "int":
        target = str(value)
        hits = [w for w in line.words
                if re.sub(r"[^\d]", "", w.text) == target and w.text.strip(".회일정 ").isdigit()
                and not (exclude and exclude[0] <= w.start < exclude[1])]
    elif kind == "date":
        digits = value.strftime("%Y%m%d") if isinstance(value, date) else re.sub(r"\D", "", str(value))
        joined = "".join(re.sub(r"\D", "", w.text) for w in line.words)
        if digits and digits in joined:
            hits = [w for w in line.words if re.sub(r"\D", "", w.text) and re.sub(r"\D", "", w.text) in digits]
    else:
        target = _norm(str(value))
        compact, owner = "", []
        for w in line.words:
            for ch in _norm(w.text):
                compact += ch
                owner.append(w)
        idx = compact.find(target) if target else -1
        if idx >= 0:
            hits = list({id(w): w for w in owner[idx:idx + len(target)]}.values())

    if not hits:
        return FieldValue(value=value, confidence=None, needs_check=True)
    conf = min(w.confidence for w in hits)
    return FieldValue(value=value, confidence=conf, needs_check=conf < NEEDS_CHECK_BELOW)


def _span_of(line: OcrLine, text: str) -> tuple[int, int] | None:
    i = line.text.find(text)
    return (i, i + len(text)) if i >= 0 else None


def fallback_dosage(times_per_day: int | None, start_date: date, *, as_needed: bool = False) -> Dosage:
    """사전으로 못 읽었을 때: 회차만 만들고 끼니·시점은 비워 needs_confirm=True."""
    n = 0 if as_needed or not times_per_day else times_per_day
    return Dosage(parsed_by=ParsedBy.RULE, needs_confirm=True, as_needed=as_needed,
                  doses=[Dose(dose_no=i + 1, meal=None, timing=None, offset_min=None) for i in range(n)],
                  cycle=Cycle(type=CycleType.DAILY, start_date=start_date))


def build_scan_drug(llm: LlmDrug, line: OcrLine | None, line_no: int, *, start_date: date,
                    match: DrugMatch, is_oral: bool | None,
                    instructions: InstructionParser) -> ScanDrug:
    """약 한 줄의 칸을 만듭니다(동기·순수). 약품 매칭은 부르는 쪽에서 미리 해서 넘깁니다."""
    name_field = build_field(llm.drug_name, line)
    name_span = _span_of(line, llm.drug_name) if line else None   # 약 이름 속 숫자(5mg)를 횟수로 잡지 않게

    dose = parse_dose_text(llm.dose_text or "")
    dose_src = build_field(llm.dose_text, line)
    dose_field = DosePerTimeField(**dose, confidence=dose_src.confidence,
                                  needs_check=dose_src.needs_check or not dose["parsed"])

    try:
        dosage = instructions.parse(llm.instruction_text, llm.times_per_day, start_date)
    except Exception:
        dosage = fallback_dosage(llm.times_per_day, start_date)

    times_field = build_field(llm.times_per_day, line, kind="int", exclude=name_span)
    if dosage.as_needed and llm.times_per_day is None:
        times_field = FieldValue(value=None, confidence=None, needs_check=False)  # 필요시 약은 비어 있어도 정상

    return ScanDrug(
        line_no=line_no,
        page_no=line.page_no if line else None,
        raw_text=line.text if line else None,       # 가린 줄
        drug_name=name_field,
        match=match,
        is_oral=is_oral,
        dose_per_time=dose_field,
        times_per_day=times_field,
        total_days=build_field(llm.total_days, line, kind="int", exclude=name_span),
        instruction_text=llm.instruction_text,
        dosage=dosage,
    )


def parse_llm_output(raw: str) -> LlmDocument:
    text = raw.strip()
    text = re.sub(r"^```(?:json)?|```$", "", text, flags=re.M).strip()
    return LlmDocument.model_validate_json(text)


async def assemble_parsed_result(doc: LlmDocument, lines: list[OcrLine], *, today: date,
                                 catalog: DrugCatalog, instructions: InstructionParser) -> dict:
    """③ LLM 결과 + ④ 줄별 규칙 → medical_documents.parsed_result(가린 값).
    drugs는 원문 줄 순서대로, 같은 약이어도 합치지 않습니다. 약품 매칭은 동시에 실행합니다."""
    by_ref = {l.ref: l for l in lines}
    order = {l.ref: i for i, l in enumerate(lines)}
    drugs_sorted = sorted(doc.drugs, key=lambda d: order.get(d.line_ref, len(order)))
    matches = await asyncio.gather(*(catalog.match(d.drug_name) for d in drugs_sorted))

    start_date = doc.prescribed_date or today
    drugs = [
        build_scan_drug(d, by_ref.get(d.line_ref), i + 1, start_date=start_date,
                        match=m, is_oral=oral, instructions=instructions).model_dump(mode="json")
        for i, (d, (m, oral)) in enumerate(zip(drugs_sorted, matches))
    ]

    def doc_field(value, kind):
        for l in lines:
            f = build_field(value, l, kind=kind)
            if f.confidence is not None:
                return f
        return build_field(value, None)

    return {
        "masked": True,
        "prompt_version": PROMPT_VERSION,
        "edited": False,
        "hospital_name": doc_field(doc.hospital_name, "text").model_dump(mode="json"),
        "prescribed_date": doc_field(doc.prescribed_date, "date").model_dump(mode="json"),
        "drugs": drugs,
    }


# ---------------------------------------------------------------------------
# 읽기 작업 (POST /scans 202 뒤, PATCH 문서 종류 다시 고르기 뒤)
# ---------------------------------------------------------------------------
@dataclass
class Deps:
    repo: ScanRepo
    ocr: OcrClient
    llm: Structurer
    catalog: DrugCatalog
    instructions: InstructionParser
    files: FileStore
    now: Callable[[], datetime]          # 시간대 있는 현재 시각(Tortoise use_tz 설정과 맞추기)


async def _retry(make_call: Callable[[], Awaitable], *, retries: int, fail: FailReason,
                 timeout: float | None = None):
    for attempt in range(retries + 1):
        try:
            return await asyncio.wait_for(make_call(), timeout)
        except Exception:
            if attempt == retries:
                raise ScanFailed(fail)


async def _check_alive(deps: Deps, scan_id: int) -> ScanDoc:
    doc = await deps.repo.get(scan_id)
    if doc.status == DocumentStatus.EXPIRED:
        raise ScanCancelled
    if is_timed_out(doc, deps.now()):
        raise ScanFailed(FailReason.TIMEOUT)
    return doc


async def run_scan_job(deps: Deps, scan_id: int, *, from_saved_lines: bool = False) -> None:
    """BackgroundTasks.add_task(run_scan_job, deps, scan_id)로 등록합니다."""
    try:
        if from_saved_lines:
            lines = [_line_from_dict(d) for d in await deps.repo.load_masked_lines(scan_id)]
        else:
            # ① 읽기 (step=reading) → ② 줄로 묶자마자 가리기
            # 가리기 전 글자는 이 함수의 메모리에만 있고, 저장·로그·LLM으로 나가지 않습니다.
            lines: list[OcrLine] = []
            for page_no, image in await deps.repo.page_images(scan_id):
                raw_lines = await _retry(lambda: deps.ocr.read_page(image), retries=OCR_MAX_RETRY,
                                         fail=FailReason.OCR_ERROR, timeout=OCR_TIMEOUT_SEC)
                lines.extend(mask_line(replace(l, page_no=page_no)) for l in raw_lines)
                await _check_alive(deps, scan_id)
            if is_no_text(lines):
                raise ScanFailed(FailReason.NO_TEXT)
            await deps.repo.save_masked_lines(scan_id, [_line_to_dict(l) for l in lines])
            await deps.repo.set_step(scan_id, ScanStep.STRUCTURING)

        # ③ 약 정보 정리 (LLM, 가린 줄만)
        doc = await _check_alive(deps, scan_id)
        numbered = [f"[{l.ref}] {l.text}" for l in lines]

        async def ask_llm() -> LlmDocument:
            return parse_llm_output(await deps.llm.structure(numbered, doc.doc_type))

        llm_doc = await _retry(ask_llm, retries=LLM_MAX_RETRY, fail=FailReason.STRUCTURE_ERROR)
        if not llm_doc.drugs:
            raise ScanFailed(FailReason.NO_DRUG_FOUND)

        # ④ 줄별 규칙 처리
        parsed = await assemble_parsed_result(llm_doc, lines, today=deps.now().date(),
                                              catalog=deps.catalog, instructions=deps.instructions)

        # ⑤ 저장 직전에 취소·시간 초과 다시 확인
        await _check_alive(deps, scan_id)
        await deps.repo.finish_ocr_done(scan_id, parsed)

    except ScanCancelled:
        return
    except ScanFailed as e:
        await _fail_unless_expired(deps, scan_id, e.reason)
    except Exception:
        # 예외 메시지·스택에 OCR 글자가 섞이지 않게 로그는 사유 코드만 남기기
        await _fail_unless_expired(deps, scan_id, FailReason.OCR_ERROR)


async def _fail_unless_expired(deps: Deps, scan_id: int, reason: FailReason) -> None:
    """Tortoise 구현은 'status가 expired가 아닐 때만' 조건부 UPDATE로 하면 확인과 변경 사이의 틈이 없습니다."""
    if (await deps.repo.get(scan_id)).status != DocumentStatus.EXPIRED:
        await deps.repo.finish_ocr_failed(scan_id, reason)


def is_no_text(lines: list[OcrLine], *, min_words: int = 5, min_avg_conf: float = 0.5) -> bool:
    """⚠ 기준값은 가상 처방전 테스트로 정함."""
    words = [w for l in lines for w in l.words if w.text]
    if len(words) < min_words:
        return True
    return sum(w.confidence for w in words) / len(words) < min_avg_conf


def is_timed_out(doc: ScanDoc, now: datetime) -> bool:
    return doc.status == DocumentStatus.UPLOADED and now - doc.processing_started_at > JOB_TIMEOUT


def _line_to_dict(l: OcrLine) -> dict:
    return {"page_no": l.page_no, "line_idx": l.line_idx,
            "words": [[w.text, w.confidence] for w in l.words]}


def _line_from_dict(d: dict) -> OcrLine:
    return make_line(d["page_no"], d["line_idx"], [OcrWord(t, c) for t, c in d["words"]])


# ---------------------------------------------------------------------------
# GET /scans/{scan_id}
# ---------------------------------------------------------------------------
async def get_scan(deps: Deps, scan_id: int, *,
                   fill_default_meals: Callable[[list[dict], int | None], list[dict]]):
    doc = await deps.repo.get(scan_id)
    if is_timed_out(doc, deps.now()):                      # 작업이 멈춰도(서버 재시작 등) 조회에서 실패로 바꿈
        await deps.repo.finish_ocr_failed(scan_id, FailReason.TIMEOUT)
        doc = await deps.repo.get(scan_id)

    if doc.status == DocumentStatus.UPLOADED:
        return ScanUploadedResponse(scan_id=scan_id, status=doc.status, step=doc.step,
                                    doc_type=doc.doc_type, image_delete_due_at=doc.image_delete_due_at)
    if doc.status == DocumentStatus.OCR_FAILED:
        return ScanOcrFailedResponse(scan_id=scan_id, status=doc.status, doc_type=doc.doc_type,
                                     fail_reason=doc.fail_reason, message=FAIL_MESSAGES[doc.fail_reason])
    if doc.status == DocumentStatus.CONFIRMED:
        return ScanConfirmedResponse(scan_id=scan_id, status=doc.status, prescription_id=doc.prescription_id)
    if doc.status == DocumentStatus.EXPIRED:
        return ScanExpiredResponse(scan_id=scan_id, status=doc.status)

    # ocr_done: 끼니 기본값은 저장하지 않고 조회할 때마다 채움(민정 fill_default_meals)
    parsed = dict(doc.parsed_result)
    drugs = []
    for d in parsed["drugs"]:
        d = dict(d)
        times = d["times_per_day"]["value"]
        d["dosage"] = {**d["dosage"], "doses": fill_default_meals(d["dosage"]["doses"], times)}
        drugs.append(d)
    return ScanOcrDoneResponse(
        scan_id=scan_id, status=doc.status, doc_type=doc.doc_type,
        image_delete_due_at=doc.image_delete_due_at,
        pages=[ScanPage(page_no=i + 1) for i in range(doc.page_count)],
        **{**parsed, "drugs": drugs},
    )


# ---------------------------------------------------------------------------
# PATCH /scans/{scan_id}
# ---------------------------------------------------------------------------
async def lookup_edit_drugs(catalog: DrugCatalog, req: ScanEditRequest) -> dict[int, tuple[str, bool | None]]:
    """apply_edits()에 넘길 약 정보를 한 번에 조회합니다."""
    ids = sorted({d.drug_id for d in (req.drugs or []) if d.drug_id is not None})
    return await catalog.get_many(ids) if ids else {}


def apply_edits(parsed: dict, req: ScanEditRequest, *, drug_lookup: dict[int, tuple[str, bool | None]],
                instructions: InstructionParser, today: date) -> dict:
    """① 고친 값 저장. 바꾼 칸만 반영하고, 고친 칸은 confidence=None·needs_check=False.
    용량을 글자로 고치면 parse_dose_text()로 다시 채우고, 복용 조건을 고르면 parsed_by=user."""
    result = {**parsed, "drugs": [dict(d) for d in parsed["drugs"]]}
    errors: dict[str, str] = {}
    user = lambda v: {"value": v, "confidence": None, "needs_check": False}

    sent = req.model_dump(exclude_unset=True)
    if "hospital_name" in sent:
        result["hospital_name"] = user(req.hospital_name)
    if "prescribed_date" in sent:
        result["prescribed_date"] = user(req.prescribed_date.isoformat() if req.prescribed_date else None)

    by_no = {d["line_no"]: d for d in result["drugs"]}
    to_delete: set[int] = set()
    next_no = max(by_no, default=0) + 1
    start_date = date.fromisoformat(result["prescribed_date"]["value"]) if result["prescribed_date"]["value"] else today

    for i, edit in enumerate(req.drugs or []):
        path = f"drugs[{i}]"
        e = edit.model_dump(exclude_unset=True)

        if edit.line_no is None:                           # 새 줄
            if not edit.drug_name:
                errors[f"{path}.drug_name"] = "약 이름을 입력해 주세요"
                continue
            drug = _new_line(next_no, start_date)
            by_no[next_no] = drug
            result["drugs"].append(drug)
            next_no += 1
        elif edit.line_no not in by_no:
            errors[f"{path}.line_no"] = "없는 약 줄이에요"
            continue
        else:
            drug = by_no[edit.line_no]

        if e.get("deleted"):
            to_delete.add(drug["line_no"])
            continue
        if "drug_name" in e:
            drug["drug_name"] = user(edit.drug_name)
        if "drug_id" in e:
            if edit.drug_id is None:
                drug["match"] = {"status": MatchStatus.NONE.value, "drug_id": None, "candidates": []}
                drug["is_oral"] = None
            else:
                found = drug_lookup.get(edit.drug_id)
                if found is None:
                    errors[f"{path}.drug_id"] = "없는 약이에요. 다시 검색해 주세요"
                    continue
                drug["match"] = {"status": MatchStatus.EXACT.value, "drug_id": edit.drug_id, "candidates": []}
                drug["is_oral"] = found[1]
        if "dose_per_time" in e:
            dose = parse_dose_text(edit.dose_per_time.text)
            # ⚠ 회원이 고친 칸은 needs_check=False가 원칙이지만, 읽을 수 없는 용량은 계속 표시
            drug["dose_per_time"] = {**dose, "confidence": None, "needs_check": not dose["parsed"]}
        if "total_days" in e:
            drug["total_days"] = user(edit.total_days)
        if "times_per_day" in e:
            drug["times_per_day"] = user(edit.times_per_day)
            if "dosage" not in e and drug["dosage"]["parsed_by"] == ParsedBy.RULE.value:
                # 회차 수가 바뀌므로 사전 결과를 새 횟수로 다시 만듦
                drug["dosage"] = _rebuild_dosage(drug, edit.times_per_day, start_date, instructions)
        if "dosage" in e:
            for j, d in enumerate(edit.dosage.doses or []):
                if d.timing is not None and d.timing not in CONFIRM_ALLOWED_TIMINGS:
                    errors[f"{path}.dosage.doses[{j}].timing"] = "식전·식후·취침 전 중에서 골라 주세요"
            new = dict(drug["dosage"])
            if edit.dosage.as_needed is not None:
                new["as_needed"] = edit.dosage.as_needed
            if edit.dosage.doses is not None:
                new["doses"] = [d.model_dump(mode="json") for d in edit.dosage.doses]
            new.update(parsed_by=ParsedBy.USER.value, needs_confirm=False)
            drug["dosage"] = new

    if errors:
        raise ScanValidationError(errors)
    result["drugs"] = [d for d in result["drugs"] if d["line_no"] not in to_delete]
    result["edited"] = True
    return result


def _new_line(line_no: int, start_date: date) -> dict:
    empty = {"value": None, "confidence": None, "needs_check": False}
    return {
        "line_no": line_no, "page_no": None, "raw_text": None,
        "drug_name": dict(empty), "match": {"status": "none", "drug_id": None, "candidates": []},
        "is_oral": None,
        "dose_per_time": {"text": "", "min": None, "max": None, "unit": None, "parsed": False,
                          "confidence": None, "needs_check": True},
        "times_per_day": dict(empty), "total_days": dict(empty), "instruction_text": None,
        "dosage": fallback_dosage(None, start_date).model_dump(mode="json"),
    }


def _rebuild_dosage(drug: dict, times: int | None, start_date: date, instructions: InstructionParser) -> dict:
    try:
        return instructions.parse(drug.get("instruction_text"), times, start_date).model_dump(mode="json")
    except Exception:
        return fallback_dosage(times, start_date).model_dump(mode="json")


def can_repick_doc_type(doc: ScanDoc) -> bool:
    if doc.status == DocumentStatus.OCR_DONE:
        return True
    return doc.status == DocumentStatus.OCR_FAILED and doc.fail_reason in DOC_TYPE_RETRY_REASONS


async def repick_doc_type(deps: Deps, scan_id: int, doc_type: DocType,
                          schedule: Callable[..., None]) -> None:
    """② 문서 종류 다시 고르기 → 202. 고친 값은 버리고, OCR 없이 가린 줄로 ③부터 다시.
    schedule에는 BackgroundTasks.add_task를 넘깁니다."""
    async with deps.repo.transaction() as conn:
        doc = await deps.repo.get(scan_id, for_update=True, conn=conn)
        if not can_repick_doc_type(doc):
            raise ScanValidationError({"doc_type": "지금은 문서 종류를 바꿀 수 없어요"})
        await deps.repo.set_reprocessing(scan_id, doc_type, deps.now(), conn=conn)  # uploaded/structuring
    schedule(run_scan_job, deps, scan_id, from_saved_lines=True)


# ---------------------------------------------------------------------------
# POST /scans/{scan_id}/confirm, DELETE /scans/{scan_id}
# ---------------------------------------------------------------------------
class ScanStateError(Exception):
    """API가 에러 코드로 바꿈: NOT_FOUND / DOCUMENT_NOT_READY / DOCUMENT_ALREADY_CONFIRMED / DOCUMENT_EXPIRED"""
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


async def confirm_scan(deps: Deps, scan_id: int, user_id: int, body: ConfirmRequest,
                       create_prescription: Callable[..., Awaitable[dict]], background_tasks=None) -> dict:
    async with deps.repo.transaction() as conn:              # 블록이 끝나면 커밋(3)
        doc = await deps.repo.get(scan_id, for_update=True, conn=conn)   # 1. 잠그고 상태·소유 확인
        if doc.user_id != user_id:
            raise ScanStateError("NOT_FOUND")
        if doc.status != DocumentStatus.OCR_DONE:
            raise ScanStateError({DocumentStatus.CONFIRMED: "DOCUMENT_ALREADY_CONFIRMED",
                                  DocumentStatus.EXPIRED: "DOCUMENT_EXPIRED"}.get(doc.status, "DOCUMENT_NOT_READY"))
        result = await create_prescription(conn, user_id, body.model_dump(mode="json"), source="ocr",
                                           background_tasks=background_tasks,
                                           medical_document_id=scan_id)   # 2. ⚠ 시그니처 민정님 확인
    await _delete_files_quietly(deps, scan_id)               # 4. 커밋 뒤, 실패해도 성공 응답
    return {"scan_id": scan_id, "status": DocumentStatus.CONFIRMED.value, **result}   # 5


async def cancel_scan(deps: Deps, scan_id: int, user_id: int) -> None:
    async with deps.repo.transaction() as conn:
        doc = await deps.repo.get(scan_id, for_update=True, conn=conn)
        if doc.user_id != user_id:
            raise ScanStateError("NOT_FOUND")
        if doc.status == DocumentStatus.CONFIRMED:
            raise ScanStateError("DOCUMENT_ALREADY_CONFIRMED")
        if doc.status == DocumentStatus.EXPIRED:
            return                                           # 여러 번 눌러도 204
        await deps.repo.expire(scan_id, conn=conn)           # 행은 남겨 하루 20회에 셈
    await _delete_files_quietly(deps, scan_id)


async def _delete_files_quietly(deps: Deps, scan_id: int) -> None:
    try:
        await deps.files.delete_pages(scan_id)
        await deps.repo.mark_pages_deleted(scan_id, deps.now())
    except Exception:
        pass                                                 # 정리 작업이 다시 지움


# ---------------------------------------------------------------------------
# 정리 작업
# ---------------------------------------------------------------------------
@dataclass
class CleanupAction:
    scan_id: int
    expire: bool        # 3시간 지난 미확정 문서 → expired로 바꾸고 지움
    delete_files: bool


def select_cleanup_actions(docs: list[ScanDoc], now: datetime) -> list[CleanupAction]:
    actions = []
    for d in docs:
        open_status = d.status in (DocumentStatus.UPLOADED, DocumentStatus.OCR_DONE, DocumentStatus.OCR_FAILED)
        if open_status and now >= d.image_delete_due_at:
            actions.append(CleanupAction(d.scan_id, expire=True, delete_files=True))
        elif d.status in (DocumentStatus.CONFIRMED, DocumentStatus.EXPIRED) and d.pages_left:
            actions.append(CleanupAction(d.scan_id, expire=False, delete_files=True))
    return actions


async def run_cleanup(deps: Deps, candidates: list[ScanDoc]) -> None:
    for a in select_cleanup_actions(candidates, deps.now()):
        if a.expire:
            async with deps.repo.transaction() as conn:
                doc = await deps.repo.get(a.scan_id, for_update=True, conn=conn)
                if doc.status in (DocumentStatus.CONFIRMED, DocumentStatus.EXPIRED):
                    continue                                 # 그사이 확정·취소됨
                await deps.repo.expire(a.scan_id, conn=conn)
        await _delete_files_quietly(deps, a.scan_id)
