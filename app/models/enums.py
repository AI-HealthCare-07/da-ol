"""ERD v2(docs/planning/daol_erd.dbml)의 Enum 정의.

DB에는 Postgres ENUM 타입이 아니라 varchar로 저장하고(CharEnumField), 허용 값은 앱에서 검사합니다.
"""

from enum import StrEnum


# ---- 회원 ----
class UserStatus(StrEnum):
    ACTIVE = "active"
    WITHDRAWN = "withdrawn"  # 탈퇴 즉시 비활성, 30일 후 영구 삭제


class SignupType(StrEnum):
    GENERAL = "general"
    PARTNER = "partner"  # [3차] 초대 링크로 들어온 파트너 간단 가입


class ConsentType(StrEnum):
    TERMS = "terms"
    PRIVACY = "privacy"
    SENSITIVE_HEALTH = "sensitive_health"  # 민감정보(건강정보) 별도 동의
    KAKAO_MESSAGE = "kakao_message"  # [2차] 카카오톡 메시지 선택 동의. 1차 로그인 때는 받지 않음
    PARTNER_SHARE = "partner_share"  # [3차]
    PARTNER_RECEIVE = "partner_receive"  # [3차]


class Gender(StrEnum):
    # ERD는 varchar(10)만 정의. 값은 API 명세 4장 기준
    MALE = "male"
    FEMALE = "female"


class DayType(StrEnum):
    WEEKDAY = "weekday"
    WEEKEND = "weekend"
    MON = "mon"
    TUE = "tue"
    WED = "wed"
    THU = "thu"
    FRI = "fri"
    SAT = "sat"
    SUN = "sun"


# ---- 의료 문서 · OCR ----
class DocumentType(StrEnum):
    PRESCRIPTION = "prescription"  # 처방전
    PILL_ENVELOPE = "pill_envelope"  # 약봉투


class DocumentStatus(StrEnum):
    UPLOADED = "uploaded"
    OCR_DONE = "ocr_done"
    OCR_FAILED = "ocr_failed"
    CONFIRMED = "confirmed"
    EXPIRED = "expired"


class OcrStatus(StrEnum):
    # document_pages.ocr_status (ERD는 varchar(20), 값: pending / done / failed)
    PENDING = "pending"
    DONE = "done"
    FAILED = "failed"


# ---- 약 마스터 ----
class DrugDataSource(StrEnum):
    EASY_DRUG = "easy_drug"  # e약은요
    PERMIT = "permit"  # 의약품 허가정보


# ---- 처방 · 복약 ----
class PrescriptionSource(StrEnum):
    OCR = "ocr"
    MANUAL = "manual"


class PrescriptionStatus(StrEnum):
    ACTIVE = "active"
    ENDED = "ended"


class CycleType(StrEnum):
    # [2차] REQ-MED-025
    DAILY = "daily"
    EVERY_OTHER_DAY = "every_other_day"
    WEEKLY_DAYS = "weekly_days"
    EVERY_N_WEEKS = "every_n_weeks"


class DoseConditionType(StrEnum):
    BEFORE_MEAL = "before_meal"
    AFTER_MEAL = "after_meal"
    BETWEEN_MEALS = "between_meals"  # [2차]
    EMPTY_STOMACH = "empty_stomach"  # [2차]
    BEDTIME = "bedtime"
    INTERVAL_HOURS = "interval_hours"  # [2차]
    AS_NEEDED = "as_needed"


class MealType(StrEnum):
    BREAKFAST = "breakfast"
    LUNCH = "lunch"
    DINNER = "dinner"


class ParsedBy(StrEnum):
    RULE = "rule"
    LLM = "llm"  # [2차]
    USER = "user"


class TimeBasis(StrEnum):
    PRESCRIPTION = "prescription"
    OFFICIAL = "official"
    NEEDS_CHECK = "needs_check"


class ScheduleStatus(StrEnum):
    OK = "ok"
    NEEDS_CHECK = "needs_check"


class IntakeStatus(StrEnum):
    PENDING = "pending"
    TAKEN = "taken"
    MISSED = "missed"


# ---- AI 가이드 · 챗봇 · RAG ----
class RagSourceType(StrEnum):
    # rag_documents.source_type (ERD는 varchar(20))
    GUIDELINE = "guideline"  # 생활습관·질환 관리 공식 자료. 1차는 이것만
    DRUG_INFO = "drug_info"  # [1차 미사용] 약 설명


class PromptKind(StrEnum):
    GUIDE_MEDICATION = "guide_medication"
    GUIDE_LIFESTYLE = "guide_lifestyle"
    CHAT = "chat"
    PARSE_CONDITION = "parse_condition"
    PARSE_DOCUMENT = "parse_document"
    SCOPE_CLASSIFY = "scope_classify"
    VERIFY = "verify"


class GuideType(StrEnum):
    MEDICATION = "medication"
    LIFESTYLE = "lifestyle"


class GuideStatus(StrEnum):
    GENERATING = "generating"  # '가이드 만드는 중'
    VERIFYING = "verifying"  # '내용 확인 중'
    COMPLETED = "completed"  # 검증 통과
    COMPLETED_WITH_REPLACEMENTS = "completed_with_replacements"  # 일부 항목을 기본 정보로 대체 (VERI-005)
    FAILED = "failed"  # 생성·검증 실패 또는 30초 초과 → 기본 약 정보 + [다시 시도]


class ChatRole(StrEnum):
    USER = "user"
    ASSISTANT = "assistant"


class ChatMessageType(StrEnum):
    NORMAL = "normal"
    EMERGENCY_PHYSICAL = "emergency_physical"  # 119 안내 후 LLM 답변 이어짐
    EMERGENCY_SELF_HARM = "emergency_self_harm"  # 109 안내만, 일반 답변 없음
    OUT_OF_SCOPE = "out_of_scope"  # 범위 밖 안내


class ChatMessageStatus(StrEnum):
    STREAMING = "streaming"
    COMPLETED = "completed"
    FAILED = "failed"  # '다시 보내기' 표시, 사용량 미차감


class ChatVerifyStatus(StrEnum):
    # [2차] VERI-007
    NOT_NEEDED = "not_needed"
    PASSED = "passed"
    CORRECTED = "corrected"  # 답변 아래 정정 안내


class LlmPurpose(StrEnum):
    GUIDE = "guide"
    CHAT = "chat"
    PARSE = "parse"
    VERIFY = "verify"
    CLASSIFY = "classify"
