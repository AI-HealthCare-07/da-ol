"""
OCR 처방 등록 입출력 계약 v1.1 — 담당: AI A 채민
API 명세서 6장(처방 등록·검증)에 맞춘 Pydantic 모델입니다. 칸 설명은 docs/planning/daol_API_명세서.md 6장을 참고하세요.

원칙
- 이 파일은 "모양"(필드 이름·타입·enum)만 정합니다.
- 1~4회, 1~365일, 1차 허용 timing, daily만 같은 업무 규칙은 명세서 4장대로
  validate_drug_input()(민정)이 검사해 VALIDATION_ERROR의 fields 형식으로 돌려줍니다.
"""
from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import Annotated, Generic, Literal, TypeVar, Union

from pydantic import BaseModel, Field

T = TypeVar("T")


# ===========================================================================
# Enum
# ===========================================================================
class DocType(str, Enum):
    PRESCRIPTION = "prescription"      # 처방전
    PILL_ENVELOPE = "pill_envelope"    # 약봉투


class DocumentStatus(str, Enum):       # ERD document_status 그대로 (6-1)
    UPLOADED = "uploaded"
    OCR_DONE = "ocr_done"
    OCR_FAILED = "ocr_failed"
    CONFIRMED = "confirmed"
    EXPIRED = "expired"


class ScanStep(str, Enum):             # 로딩 문구용 (uploaded일 때만)
    READING = "reading"
    STRUCTURING = "structuring"


class FailReason(str, Enum):
    OCR_ERROR = "ocr_error"
    NO_TEXT = "no_text"
    NO_DRUG_FOUND = "no_drug_found"
    STRUCTURE_ERROR = "structure_error"
    TIMEOUT = "timeout"


# 서버가 내려주는 화면 문구 (6-1). 프론트는 그대로 띄웁니다.
FAIL_MESSAGES: dict[FailReason, str] = {
    FailReason.OCR_ERROR: "인식에 실패했어요. 잠시 후 다시 올리거나 직접 입력해 주세요",
    FailReason.NO_TEXT: "글자를 읽지 못했어요. 밝은 곳에서 문서 전체가 나오게 다시 찍어 주세요",
    FailReason.NO_DRUG_FOUND: "약 정보를 찾지 못했어요. 문서 종류를 다시 고르거나 직접 입력해 주세요",
    FailReason.STRUCTURE_ERROR: "약 정보를 정리하지 못했어요. 직접 입력해 주세요",
    FailReason.TIMEOUT: "인식에 실패했어요. 잠시 후 다시 올리거나 직접 입력해 주세요",
}

# 문서 종류 다시 고르기를 받는 실패 사유 (PATCH 비고)
DOC_TYPE_RETRY_REASONS = {FailReason.NO_DRUG_FOUND, FailReason.STRUCTURE_ERROR}


class MatchStatus(str, Enum):
    EXACT = "exact"
    CANDIDATES = "candidates"
    NONE = "none"


class Meal(str, Enum):
    BREAKFAST = "breakfast"
    LUNCH = "lunch"
    DINNER = "dinner"


class Timing(str, Enum):
    # 1차 확정 허용 값
    AFTER_MEAL = "after_meal"
    BEFORE_MEAL = "before_meal"
    BEDTIME = "bedtime"
    # 인식 단계에서만 나올 수 있음 → needs_confirm: true, 확정 때는 거절
    BETWEEN_MEALS = "between_meals"
    EMPTY_STOMACH = "empty_stomach"
    INTERVAL = "interval"


CONFIRM_ALLOWED_TIMINGS = {Timing.AFTER_MEAL, Timing.BEFORE_MEAL, Timing.BEDTIME}


class ParsedBy(str, Enum):
    RULE = "rule"    # 표현 사전
    USER = "user"    # 회원이 고름 (llm은 2차)


class CycleType(str, Enum):
    DAILY = "daily"                       # 1차는 daily만 시간표 계산
    EVERY_OTHER_DAY = "every_other_day"   # 인식되면 needs_confirm: true
    WEEKLY = "weekly"                     # 〃


class ConditionReason(str, Enum):
    TIMING_UNKNOWN = "timing_unknown"
    MEAL_UNKNOWN = "meal_unknown"


class ScanErrorCode(str, Enum):           # 6-3 + 이 영역에서 쓰는 1-1 공통 코드
    VALIDATION_ERROR = "VALIDATION_ERROR"
    NOT_FOUND = "NOT_FOUND"
    RATE_LIMITED = "RATE_LIMITED"
    FILE_TOO_LARGE = "FILE_TOO_LARGE"
    UNSUPPORTED_FILE_TYPE = "UNSUPPORTED_FILE_TYPE"
    ENCRYPTED_PDF = "ENCRYPTED_PDF"
    INVALID_FILE = "INVALID_FILE"
    TOO_MANY_PAGES = "TOO_MANY_PAGES"
    DOCUMENT_NOT_READY = "DOCUMENT_NOT_READY"
    DOCUMENT_ALREADY_CONFIRMED = "DOCUMENT_ALREADY_CONFIRMED"
    DOCUMENT_EXPIRED = "DOCUMENT_EXPIRED"


# ===========================================================================
# 공통 조각 (6-2)
# ===========================================================================
class FieldValue(BaseModel, Generic[T]):
    """OCR에서 읽은 칸. needs_check가 true인 칸만 노란색으로 표시합니다."""
    value: T
    confidence: float | None = Field(..., ge=0, le=1)   # 원문과 달라졌거나 회원이 고친 칸은 null
    needs_check: bool


class DosePerTime(BaseModel):
    """parse_dose_text()(6-4) 출력과 같은 모양."""
    text: str
    min: float | None
    max: float | None
    unit: str | None
    parsed: bool


class DosePerTimeField(DosePerTime):
    """인식 결과의 1회 용량. parsed: false면 needs_check: true.
    회원이 PATCH로 고친 용량이면 edited: true(고친 용량을 읽을 수 없으면 needs_check도 true, 6-2 예외)."""
    confidence: float | None = Field(..., ge=0, le=1)
    needs_check: bool
    edited: bool = False   # 프론트가 고친 용량과 OCR 용량의 안내 문구를 나누는 데 씀(11/25 설아)


class DrugCandidate(BaseModel):
    drug_id: int
    item_name: str
    company: str | None
    similarity: float


class DrugMatch(BaseModel):
    status: MatchStatus
    drug_id: int | None                                   # exact일 때만 채워짐
    candidates: list[DrugCandidate] = Field(default_factory=list, max_length=3)


class Dose(BaseModel):
    dose_no: int = Field(..., ge=1)
    meal: Meal | None
    timing: Timing | None
    offset_min: int | None                                # 원문에 없으면 null


class Cycle(BaseModel):
    type: CycleType
    start_date: date                                      # 처방일을 읽었으면 처방일, 아니면 오늘


class Dosage(BaseModel):
    parsed_by: ParsedBy
    needs_confirm: bool
    as_needed: bool
    doses: list[Dose]
    cycle: Cycle


class ScanDrug(BaseModel):
    """인식 결과의 약 한 줄. 원문 줄 순서(line_no)대로, 같은 약이어도 합치지 않습니다."""
    line_no: int
    page_no: int | None                                   # 회원이 새로 추가한 줄은 null
    raw_text: str | None                                  # 가린 원문 줄. 새로 추가한 줄은 null
    drug_name: FieldValue[str]
    match: DrugMatch
    is_oral: bool | None
    dose_per_time: DosePerTimeField
    times_per_day: FieldValue[int | None]                 # 필요시 약만 null 가능
    total_days: FieldValue[int | None]
    instruction_text: str | None
    dosage: Dosage


class ScanPage(BaseModel):
    page_no: int


# ===========================================================================
# POST /scans → 202
# ===========================================================================
class ScanCreatedResponse(BaseModel):
    scan_id: int
    status: Literal[DocumentStatus.UPLOADED]
    step: Literal[ScanStep.READING]
    doc_type: DocType
    page_count: int
    image_delete_due_at: datetime                         # 업로드 + 3시간, 연장 없음


# ===========================================================================
# GET /scans/{scan_id} → 200 (status별 모양)
# ===========================================================================
class ScanUploadedResponse(BaseModel):
    scan_id: int
    status: Literal[DocumentStatus.UPLOADED]
    step: ScanStep
    doc_type: DocType
    image_delete_due_at: datetime


class ScanOcrDoneResponse(BaseModel):
    scan_id: int
    status: Literal[DocumentStatus.OCR_DONE]
    step: None = None
    doc_type: DocType
    image_delete_due_at: datetime
    pages: list[ScanPage]
    masked: bool
    prompt_version: str                                   # "parse_document_v1"
    edited: bool
    hospital_name: FieldValue[str | None]
    prescribed_date: FieldValue[date | None]
    drugs: list[ScanDrug]


class ScanOcrFailedResponse(BaseModel):
    scan_id: int
    status: Literal[DocumentStatus.OCR_FAILED]
    step: None = None
    doc_type: DocType
    fail_reason: FailReason
    message: str


class ScanConfirmedResponse(BaseModel):
    scan_id: int
    status: Literal[DocumentStatus.CONFIRMED]
    step: None = None
    prescription_id: int                                  # prescriptions.document_id로 찾음


class ScanExpiredResponse(BaseModel):
    scan_id: int
    status: Literal[DocumentStatus.EXPIRED]
    step: None = None


ScanStatusResponse = Annotated[
    Union[ScanUploadedResponse, ScanOcrDoneResponse, ScanOcrFailedResponse,
          ScanConfirmedResponse, ScanExpiredResponse],
    Field(discriminator="status"),
]


# ===========================================================================
# PATCH /scans/{scan_id} — 둘 중 하나만 (둘 다 보내면 VALIDATION_ERROR)
# ===========================================================================
class DosePerTimeInput(BaseModel):
    text: str                                             # 서버가 parse_dose_text()로 나머지를 채움


class DosageEdit(BaseModel):
    """회원이 고른 복용 조건. 저장하면 parsed_by: user, needs_confirm: false."""
    as_needed: bool | None = None
    doses: list[Dose] | None = None


class ScanDrugEdit(BaseModel):
    """바꾼 칸만 보냅니다. 기존 줄은 line_no, 새 줄은 line_no 없이, 지울 줄은 deleted: true."""
    line_no: int | None = None
    deleted: bool | None = None
    drug_id: int | None = None
    drug_name: str | None = None
    dose_per_time: DosePerTimeInput | None = None
    times_per_day: int | None = None
    total_days: int | None = None
    dosage: DosageEdit | None = None


class ScanEditRequest(BaseModel):                         # ① 고친 값 저장 → 200 (ocr_done 모양, edited: true)
    hospital_name: str | None = None
    prescribed_date: date | None = None
    drugs: list[ScanDrugEdit] | None = None


class ScanDocTypeRequest(BaseModel):                      # ② 문서 종류 다시 고르기 → 202
    doc_type: DocType


class ScanDocTypeResponse(BaseModel):
    scan_id: int
    status: Literal[DocumentStatus.UPLOADED]
    step: Literal[ScanStep.STRUCTURING]
    doc_type: DocType


# ===========================================================================
# POST /scans/{scan_id}/confirm → 201  (이 Body가 create_prescription() 입력)
# ===========================================================================
class ConfirmDosage(BaseModel):
    parsed_by: ParsedBy
    as_needed: bool
    doses: list[Dose]
    cycle: Cycle


class ConfirmDrug(BaseModel):
    line_no: int | None = None                            # OCR만. 저장하지 않음
    drug_id: int | None                                   # 공공데이터에 없는 약은 null
    drug_name: str                                        # → prescription_items.drug_name_raw
    raw_text: str | None = None                           # 가린 원문 줄 → source_text. 새 줄은 null
    dose_per_time: DosePerTime                            # ERD에는 text만 저장
    times_per_day: int | None                             # as_needed면 null 가능
    total_days: int
    instruction_text: str | None = None
    dosage: ConfirmDosage


class ConfirmRequest(BaseModel):
    hospital_name: str | None = None
    prescribed_date: date | None = None
    drugs: list[ConfirmDrug]


class ConditionToConfirm(BaseModel):
    condition_id: int
    prescription_item_id: int
    drug_name: str
    dose_no: int
    reason: ConditionReason


class ConfirmResponse(BaseModel):
    scan_id: int
    status: Literal[DocumentStatus.CONFIRMED]
    prescription_id: int
    conditions_to_confirm: list[ConditionToConfirm]


# ===========================================================================
# 에러 (1-1)
# ===========================================================================
class ErrorResponse(BaseModel):
    code: ScanErrorCode
    message: str
    fields: dict[str, str] | None = None                  # {"drugs[1].total_days": "사유 문장"}
