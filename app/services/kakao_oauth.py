"""카카오 로그인 REST API 클라이언트 (명세 4-1 [POST] /auth/kakao).

인가 코드 → 카카오 토큰 → 사용자 정보 순서로 부릅니다. 카카오 토큰은 1차에 저장하지 않으므로(4-8) 사용자 정보를 받은 뒤 버립니다.
"""

from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass
from typing import Any

import httpx
from starlette import status

from app.core import config
from app.core.exceptions import AppError, ErrorCode

KAKAO_TOKEN_URL = "https://kauth.kakao.com/oauth/token"
KAKAO_USER_URL = "https://kapi.kakao.com/v2/user/me"

KAKAO_LOGIN_FAILED_MESSAGE = "카카오 로그인에 실패했어요. 다시 시도해 주세요"


@dataclass(frozen=True)
class KakaoUser:
    kakao_id: str
    nickname: str | None
    email: str | None


def kakao_auth_failed() -> AppError:
    return AppError(status.HTTP_401_UNAUTHORIZED, ErrorCode.KAKAO_AUTH_FAILED, KAKAO_LOGIN_FAILED_MESSAGE)


def kakao_unavailable() -> AppError:
    return AppError(status.HTTP_502_BAD_GATEWAY, ErrorCode.EXTERNAL_API_ERROR, KAKAO_LOGIN_FAILED_MESSAGE)


def parse_kakao_user(data: dict[str, Any]) -> KakaoUser:
    """`/v2/user/me` 응답에서 회원번호·닉네임·이메일만 꺼냅니다. 이메일은 동의했고 유효·인증된 경우만 씁니다."""
    kakao_id = data.get("id")
    if kakao_id is None:
        raise kakao_auth_failed()

    account = data.get("kakao_account") or {}
    profile = account.get("profile") or {}
    nickname = profile.get("nickname") or (data.get("properties") or {}).get("nickname")

    email = account.get("email")
    if not (email and account.get("is_email_valid") and account.get("is_email_verified")):
        email = None

    return KakaoUser(kakao_id=str(kakao_id), nickname=nickname, email=email)


class KakaoOAuthClient:
    def __init__(self, http_client: httpx.AsyncClient | None = None) -> None:
        self._http_client = http_client

    async def fetch_user(self, code: str) -> KakaoUser:
        async with self._client() as client:
            access_token = await self._exchange_code(client, code)
            return await self._get_user(client, access_token)

    def _client(self) -> AbstractAsyncContextManager[httpx.AsyncClient]:
        if self._http_client is not None:
            return _NonClosingClient(self._http_client)
        return httpx.AsyncClient(timeout=config.KAKAO_TIMEOUT_SECONDS)

    async def _exchange_code(self, client: httpx.AsyncClient, code: str) -> str:
        form = {
            "grant_type": "authorization_code",
            "client_id": config.KAKAO_REST_API_KEY,
            "redirect_uri": config.KAKAO_REDIRECT_URI,
            "code": code,
        }
        if config.KAKAO_CLIENT_SECRET:
            form["client_secret"] = config.KAKAO_CLIENT_SECRET

        data = await self._send(client, "POST", KAKAO_TOKEN_URL, data=form)
        access_token = data.get("access_token")
        if not access_token:
            raise kakao_auth_failed()
        return str(access_token)

    async def _get_user(self, client: httpx.AsyncClient, access_token: str) -> KakaoUser:
        data = await self._send(client, "GET", KAKAO_USER_URL, headers={"Authorization": f"Bearer {access_token}"})
        return parse_kakao_user(data)

    @staticmethod
    async def _send(client: httpx.AsyncClient, method: str, url: str, **kwargs: Any) -> dict[str, Any]:
        try:
            response = await client.request(method, url, **kwargs)
        except httpx.HTTPError as err:  # 타임아웃·연결 실패
            raise kakao_unavailable() from err

        if response.status_code >= 500:
            raise kakao_unavailable()
        if response.status_code >= 400:  # 잘못됐거나 만료된 인가 코드, 키·리다이렉트 주소 불일치
            raise kakao_auth_failed()

        try:
            data = response.json()
        except ValueError as err:
            raise kakao_unavailable() from err
        if not isinstance(data, dict):
            raise kakao_unavailable()
        return data


class _NonClosingClient:
    """주입받은 httpx 클라이언트를 `async with`로 써도 닫지 않게 감쌉니다(테스트용)."""

    def __init__(self, client: httpx.AsyncClient) -> None:
        self._client = client

    async def __aenter__(self) -> httpx.AsyncClient:
        return self._client

    async def __aexit__(self, *_exc: object) -> None:
        return None


def get_kakao_client() -> KakaoOAuthClient:
    return KakaoOAuthClient()
