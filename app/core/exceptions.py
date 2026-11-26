"""명세 1-1 에러 응답 형식 `{"code": ..., "message": ...}`을 내려주는 공용 예외."""

from enum import StrEnum
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import ORJSONResponse


class ErrorCode(StrEnum):
    """에러 코드. 프론트가 이 값으로 화면 처리를 나누므로 글자로 직접 쓰지 않고 여기서 꺼내 씁니다."""

    # 1-1 공통
    UNAUTHORIZED = "UNAUTHORIZED"
    PROFILE_REQUIRED = "PROFILE_REQUIRED"
    NOT_FOUND = "NOT_FOUND"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    RATE_LIMITED = "RATE_LIMITED"
    EXTERNAL_API_ERROR = "EXTERNAL_API_ERROR"
    INTERNAL_ERROR = "INTERNAL_ERROR"

    # 4-0 인증·회원 / 복용 기록 / 처방 직접 입력
    KAKAO_AUTH_FAILED = "KAKAO_AUTH_FAILED"
    REJOIN_RESTRICTED = "REJOIN_RESTRICTED"
    REFRESH_TOKEN_EXPIRED = "REFRESH_TOKEN_EXPIRED"
    PROFILE_ALREADY_COMPLETED = "PROFILE_ALREADY_COMPLETED"
    INTAKE_EDIT_EXPIRED = "INTAKE_EDIT_EXPIRED"
    INTAKE_FUTURE_DATE = "INTAKE_FUTURE_DATE"
    DRUG_NOT_FOUND = "DRUG_NOT_FOUND"
    PRESCRIPTION_ALREADY_ENDED = "PRESCRIPTION_ALREADY_ENDED"


class AppError(Exception):
    """API에서 1-1 형식으로 응답할 에러. `extra`는 응답 본문에 그대로 더해집니다(예: `rejoin_available_date`)."""

    def __init__(self, status_code: int, code: ErrorCode, message: str, extra: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.extra = extra or {}


async def app_error_handler(_request: Request, exc: Exception) -> ORJSONResponse:
    assert isinstance(exc, AppError)
    return ORJSONResponse(
        status_code=exc.status_code,
        content={"code": exc.code.value, "message": exc.message, **exc.extra},
    )


# ---- 422 입력 오류 (명세 1-1 VALIDATION_ERROR) ----
VALIDATION_MESSAGE = "입력한 내용을 확인해 주세요"
DEFAULT_FIELD_MESSAGE = "형식이 맞지 않아요"
LOC_PREFIXES = ("body", "query", "path", "header", "cookie")

# pydantic 에러 종류 → 칸별 문구. 표에 없는 종류는 DEFAULT_FIELD_MESSAGE.
FIELD_MESSAGES: dict[str, str] = {
    "missing": "필수 항목이에요",
    "string_too_short": "{min_length}자 이상 입력해 주세요",
    "string_too_long": "{max_length}자 이하로 입력해 주세요",
    "too_short": "{min_length}개 이상 입력해 주세요",
    "too_long": "{max_length}개 이하로 입력해 주세요",
    "greater_than": "{gt}보다 큰 값을 입력해 주세요",
    "greater_than_equal": "{ge} 이상으로 입력해 주세요",
    "less_than": "{lt}보다 작은 값을 입력해 주세요",
    "less_than_equal": "{le} 이하로 입력해 주세요",
    "enum": "선택할 수 있는 값이 아니에요",
    "literal_error": "선택할 수 있는 값이 아니에요",
    "date_from_datetime_parsing": "날짜 형식이 맞지 않아요",
    "date_parsing": "날짜 형식이 맞지 않아요",
    "date_type": "날짜 형식이 맞지 않아요",
    "int_parsing": "숫자를 입력해 주세요",
    "int_type": "숫자를 입력해 주세요",
    "float_parsing": "숫자를 입력해 주세요",
    "float_type": "숫자를 입력해 주세요",
    "decimal_parsing": "숫자를 입력해 주세요",
    "bool_parsing": "참/거짓 값이 아니에요",
    "json_invalid": "요청 형식이 맞지 않아요",
}


def field_key(loc: tuple[int | str, ...]) -> str:
    """("body", "drugs", 0, "dose_per_time") → "drugs[0].dose_per_time" (목록 순번은 대괄호)."""
    key = ""
    for i, part in enumerate(loc):
        if i == 0 and part in LOC_PREFIXES:
            continue
        if isinstance(part, int):
            key += f"[{part}]"
        else:
            key += f".{part}" if key else str(part)
    return key or "body"


def field_message(error: dict[str, Any]) -> str:
    template = FIELD_MESSAGES.get(error.get("type", ""))
    if template is None:
        return DEFAULT_FIELD_MESSAGE
    try:
        return template.format(**(error.get("ctx") or {}))
    except (KeyError, IndexError):
        return DEFAULT_FIELD_MESSAGE


async def validation_error_handler(_request: Request, exc: Exception) -> ORJSONResponse:
    assert isinstance(exc, RequestValidationError)
    fields: dict[str, str] = {}
    for error in exc.errors():
        key = field_key(tuple(error.get("loc", ())))
        fields.setdefault(key, field_message(error))  # 한 칸에 여러 개면 첫 번째 사유만
    return ORJSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        content={"code": ErrorCode.VALIDATION_ERROR.value, "message": VALIDATION_MESSAGE, "fields": fields},
    )


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppError, app_error_handler)
    app.add_exception_handler(RequestValidationError, validation_error_handler)
