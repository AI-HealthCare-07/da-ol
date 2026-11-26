"""명세 1-1 에러 응답 형식 `{"code": ..., "message": ...}`을 내려주는 공용 예외."""

from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import ORJSONResponse


class AppError(Exception):
    """API에서 1-1 형식으로 응답할 에러. `extra`는 응답 본문에 그대로 더해집니다(예: `rejoin_available_date`)."""

    def __init__(self, status_code: int, code: str, message: str, extra: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.extra = extra or {}


async def app_error_handler(_request: Request, exc: Exception) -> ORJSONResponse:
    assert isinstance(exc, AppError)
    return ORJSONResponse(
        status_code=exc.status_code,
        content={"code": exc.code, "message": exc.message, **exc.extra},
    )


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppError, app_error_handler)
