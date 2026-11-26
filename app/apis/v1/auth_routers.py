from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, Response, status

from app.core import config
from app.dependencies.security import get_request_user
from app.dtos.auth import KakaoLoginRequest, KakaoLoginResponse, LoginUser, TokenRefreshResponse
from app.models.users import User
from app.services.auth_service import AuthService
from app.services.kakao_oauth import KakaoOAuthClient, get_kakao_client

auth_router = APIRouter(prefix="/auth", tags=["auth"])

# 명세 4-1: HttpOnly; Secure; SameSite=Lax; Path=/api/v1/auth; Max-Age=14일. Domain은 넣지 않습니다(호스트 전용 쿠키).
REFRESH_COOKIE_NAME = "refresh_token"
REFRESH_COOKIE_PATH = "/api/v1/auth"
REFRESH_COOKIE_MAX_AGE = config.REFRESH_TOKEN_EXPIRE_MINUTES * 60
ACCESS_TOKEN_EXPIRES_IN = config.ACCESS_TOKEN_EXPIRE_MINUTES * 60


def get_auth_service(kakao_client: Annotated[KakaoOAuthClient, Depends(get_kakao_client)]) -> AuthService:
    return AuthService(kakao_client=kakao_client)


def set_refresh_cookie(response: Response, raw: str) -> None:
    response.set_cookie(
        REFRESH_COOKIE_NAME,
        raw,
        max_age=REFRESH_COOKIE_MAX_AGE,
        path=REFRESH_COOKIE_PATH,
        httponly=True,
        secure=True,
        samesite="lax",
    )


def delete_refresh_cookie(response: Response) -> None:
    response.set_cookie(
        REFRESH_COOKIE_NAME, "", max_age=0, path=REFRESH_COOKIE_PATH, httponly=True, secure=True, samesite="lax"
    )


@auth_router.post("/kakao", response_model=KakaoLoginResponse, status_code=status.HTTP_200_OK)
async def kakao_login(
    body: KakaoLoginRequest,
    response: Response,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> KakaoLoginResponse:
    result = await auth_service.kakao_login(body.code)
    set_refresh_cookie(response, result.tokens.refresh_token)
    return KakaoLoginResponse(
        access_token=result.tokens.access_token,
        expires_in=ACCESS_TOKEN_EXPIRES_IN,
        is_new_user=result.is_new_user,
        is_profile_completed=result.user.is_profile_completed,
        user=LoginUser(user_id=result.user.id, nickname=result.user.nickname),
    )


@auth_router.post("/refresh", response_model=TokenRefreshResponse, status_code=status.HTTP_200_OK)
async def refresh(
    response: Response,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
    refresh_token: Annotated[str | None, Cookie()] = None,
) -> TokenRefreshResponse:
    tokens = await auth_service.refresh(refresh_token)
    set_refresh_cookie(response, tokens.refresh_token)
    return TokenRefreshResponse(access_token=tokens.access_token, expires_in=ACCESS_TOKEN_EXPIRES_IN)


@auth_router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    user: Annotated[User, Depends(get_request_user)],
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
    refresh_token: Annotated[str | None, Cookie()] = None,
) -> Response:
    await auth_service.logout(user, refresh_token)
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    delete_refresh_cookie(response)
    return response
