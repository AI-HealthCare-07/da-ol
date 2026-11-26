"""POST /auth/kakao · /auth/refresh · /auth/logout (명세 4-1). 카카오 호출은 가짜 클라이언트로 바꿉니다."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import timedelta

from httpx import ASGITransport, AsyncClient
from starlette import status
from tortoise import timezone
from tortoise.contrib.test import TestCase

from app.core.exceptions import AppError
from app.main import app
from app.models.enums import UserStatus
from app.models.users import RefreshToken, User
from app.services.auth_service import hash_refresh_token
from app.services.kakao_oauth import KakaoUser, get_kakao_client, kakao_auth_failed

# 쿠키에 Secure가 붙어 있어서 https 주소로 불러야 클라이언트가 쿠키를 다시 보냅니다.
BASE_URL = "https://test"


class FakeKakaoClient:
    def __init__(self, user: KakaoUser | None = None, error: AppError | None = None) -> None:
        self.user = user
        self.error = error

    async def fetch_user(self, code: str) -> KakaoUser:
        if self.error is not None:
            raise self.error
        assert self.user is not None
        return self.user


@asynccontextmanager
async def client_with_kakao(fake: FakeKakaoClient) -> AsyncIterator[AsyncClient]:
    app.dependency_overrides[get_kakao_client] = lambda: fake
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE_URL) as client:
            yield client
    finally:
        app.dependency_overrides.pop(get_kakao_client, None)


def kakao_user(kakao_id: str = "1001", nickname: str | None = "다올이", email: str | None = None) -> KakaoUser:
    return KakaoUser(kakao_id=kakao_id, nickname=nickname, email=email)


class TestKakaoLogin(TestCase):
    async def test_new_user_signup(self):
        fake = FakeKakaoClient(kakao_user(email="daol@example.com"))
        async with client_with_kakao(fake) as client:
            response = await client.post("/api/v1/auth/kakao", json={"code": "abc"})

        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert body["token_type"] == "Bearer"
        assert body["expires_in"] == 1800
        assert body["is_new_user"] is True
        assert body["is_profile_completed"] is False
        assert body["user"]["nickname"] == "다올이"

        user = await User.get(kakao_id="1001")
        assert body["user"]["user_id"] == user.id
        assert user.email == "daol@example.com"

        cookie = response.headers["set-cookie"]
        assert "refresh_token=" in cookie
        assert "HttpOnly" in cookie
        assert "Secure" in cookie
        assert "samesite=lax" in cookie.lower()
        assert "Path=/api/v1/auth" in cookie
        assert "Max-Age=1209600" in cookie
        assert "Domain" not in cookie

        raw = response.cookies["refresh_token"]
        stored = await RefreshToken.get(token_hash=hash_refresh_token(raw))
        assert stored.user_id == user.id  # type: ignore[attr-defined]
        assert raw not in stored.token_hash  # 원문은 저장하지 않음

    async def test_existing_user_login(self):
        user = await User.create(kakao_id="1002", nickname="기존회원", is_profile_completed=True)
        async with client_with_kakao(FakeKakaoClient(kakao_user("1002", "바뀐닉네임"))) as client:
            response = await client.post("/api/v1/auth/kakao", json={"code": "abc"})

        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert body["is_new_user"] is False
        assert body["is_profile_completed"] is True
        assert body["user"] == {"user_id": user.id, "nickname": "기존회원"}

    async def test_duplicate_nickname_gets_suffix(self):
        await User.create(kakao_id="1003", nickname="다올이")
        async with client_with_kakao(FakeKakaoClient(kakao_user("1004", "다올이"))) as client:
            response = await client.post("/api/v1/auth/kakao", json={"code": "abc"})

        nickname = response.json()["user"]["nickname"]
        assert nickname.startswith("다올이")
        assert len(nickname) == 7

    async def test_kakao_auth_failed(self):
        async with client_with_kakao(FakeKakaoClient(error=kakao_auth_failed())) as client:
            response = await client.post("/api/v1/auth/kakao", json={"code": "bad"})

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert response.json()["code"] == "KAKAO_AUTH_FAILED"

    async def test_missing_code(self):
        async with client_with_kakao(FakeKakaoClient(kakao_user())) as client:
            response = await client.post("/api/v1/auth/kakao", json={})
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        assert response.json() == {
            "code": "VALIDATION_ERROR",
            "message": "입력한 내용을 확인해 주세요",
            "fields": {"code": "필수 항목이에요"},
        }

    async def test_rejoin_restricted_within_30_days(self):
        await User.create(
            kakao_id="1005",
            nickname="탈퇴회원",
            status=UserStatus.WITHDRAWN,
            withdrawn_at=timezone.now() - timedelta(days=10),
        )
        async with client_with_kakao(FakeKakaoClient(kakao_user("1005"))) as client:
            response = await client.post("/api/v1/auth/kakao", json={"code": "abc"})

        assert response.status_code == status.HTTP_403_FORBIDDEN
        body = response.json()
        assert body["code"] == "REJOIN_RESTRICTED"
        assert "rejoin_available_date" in body

    async def test_rejoin_allowed_after_30_days(self):
        old = await User.create(
            kakao_id="1006",
            nickname="옛회원",
            status=UserStatus.WITHDRAWN,
            withdrawn_at=timezone.now() - timedelta(days=31),
        )
        async with client_with_kakao(FakeKakaoClient(kakao_user("1006", "새회원"))) as client:
            response = await client.post("/api/v1/auth/kakao", json={"code": "abc"})

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["is_new_user"] is True
        assert not await User.filter(id=old.id).exists()


class TestRefreshAndLogout(TestCase):
    async def _login(self, client: AsyncClient) -> dict:
        response = await client.post("/api/v1/auth/kakao", json={"code": "abc"})
        assert response.status_code == status.HTTP_200_OK
        return response.json()

    async def test_refresh_rotates_token(self):
        async with client_with_kakao(FakeKakaoClient(kakao_user("2001"))) as client:
            await self._login(client)
            old_raw = client.cookies["refresh_token"]

            response = await client.post("/api/v1/auth/refresh")

        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert body["token_type"] == "Bearer"
        assert body["expires_in"] == 1800
        new_raw = response.cookies["refresh_token"]
        assert new_raw != old_raw

        old = await RefreshToken.get(token_hash=hash_refresh_token(old_raw))
        new = await RefreshToken.get(token_hash=hash_refresh_token(new_raw))
        assert old.revoked_at is not None
        assert new.revoked_at is None

    async def test_refresh_without_cookie(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE_URL) as client:
            response = await client.post("/api/v1/auth/refresh")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert response.json() == {"code": "REFRESH_TOKEN_EXPIRED", "message": "로그인이 만료되었습니다"}

    async def test_reused_token_revokes_all(self):
        async with client_with_kakao(FakeKakaoClient(kakao_user("2002"))) as client:
            await self._login(client)
            old_raw = client.cookies["refresh_token"]
            await client.post("/api/v1/auth/refresh")  # 정상 회전

            client.cookies.clear()
            response = await client.post(  # 이미 쓴 토큰 재사용
                "/api/v1/auth/refresh", headers={"Cookie": f"refresh_token={old_raw}"}
            )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert response.json()["code"] == "REFRESH_TOKEN_EXPIRED"
        user = await User.get(kakao_id="2002")
        assert not await RefreshToken.filter(user_id=user.id, revoked_at__isnull=True).exists()

    async def test_expired_refresh_token(self):
        async with client_with_kakao(FakeKakaoClient(kakao_user("2003"))) as client:
            await self._login(client)
            raw = client.cookies["refresh_token"]
            await RefreshToken.filter(token_hash=hash_refresh_token(raw)).update(
                expires_at=timezone.now() - timedelta(seconds=1)
            )
            response = await client.post("/api/v1/auth/refresh")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert response.json()["code"] == "REFRESH_TOKEN_EXPIRED"

    async def test_withdrawn_user_cannot_refresh(self):
        async with client_with_kakao(FakeKakaoClient(kakao_user("2004"))) as client:
            await self._login(client)
            await User.filter(kakao_id="2004").update(status=UserStatus.WITHDRAWN, withdrawn_at=timezone.now())
            response = await client.post("/api/v1/auth/refresh")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert response.json()["code"] == "REFRESH_TOKEN_EXPIRED"

    async def test_logout_revokes_only_this_device(self):
        async with client_with_kakao(FakeKakaoClient(kakao_user("2005"))) as other_device:
            await self._login(other_device)
            other_raw = other_device.cookies["refresh_token"]

        async with client_with_kakao(FakeKakaoClient(kakao_user("2005"))) as client:
            body = await self._login(client)
            raw = client.cookies["refresh_token"]
            headers = {"Authorization": f"Bearer {body['access_token']}"}

            response = await client.post("/api/v1/auth/logout", headers=headers)
            assert response.status_code == status.HTTP_204_NO_CONTENT
            assert "Max-Age=0" in response.headers["set-cookie"]

            again = await client.post("/api/v1/auth/logout", headers=headers)  # 두 번 눌러도 204
            assert again.status_code == status.HTTP_204_NO_CONTENT

        assert (await RefreshToken.get(token_hash=hash_refresh_token(raw))).revoked_at is not None
        assert (await RefreshToken.get(token_hash=hash_refresh_token(other_raw))).revoked_at is None

    async def test_logout_requires_access_token(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE_URL) as client:
            no_header = await client.post("/api/v1/auth/logout")
            bad_token = await client.post("/api/v1/auth/logout", headers={"Authorization": "Bearer nope"})

        for response in (no_header, bad_token):
            assert response.status_code == status.HTTP_401_UNAUTHORIZED
            assert response.json()["code"] == "UNAUTHORIZED"
