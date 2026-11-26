"""로그인한 회원을 꺼내는 의존성. 인증이 필요한 API는 `Depends(get_request_user)`를 씁니다."""

from typing import Annotated

from fastapi import Depends, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.exceptions import AppError
from app.core.jwt.exceptions import TokenError
from app.core.jwt.tokens import AccessToken
from app.models.enums import UserStatus
from app.models.users import User

# auto_error=False: 헤더가 없을 때 FastAPI 기본 403 대신 명세 1-1의 UNAUTHORIZED(401)를 내려줍니다.
security = HTTPBearer(auto_error=False)


def unauthorized() -> AppError:
    return AppError(status.HTTP_401_UNAUTHORIZED, "UNAUTHORIZED", "로그인이 필요해요")


async def get_request_user(
    credential: Annotated[HTTPAuthorizationCredentials | None, Depends(security)],
) -> User:
    if credential is None:
        raise unauthorized()
    try:
        token = AccessToken(token=credential.credentials)
    except TokenError as err:  # 만료·위조·형식 오류
        raise unauthorized() from err
    if token.payload.get("type") != AccessToken.token_type:
        raise unauthorized()

    user = await User.get_or_none(id=token.payload.get("user_id"))
    if user is None or user.status == UserStatus.WITHDRAWN:
        raise unauthorized()
    return user
