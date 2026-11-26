from httpx import ASGITransport, AsyncClient
from starlette import status
from tortoise.contrib.test import TestCase

from app.main import app
from app.models.users import User
from app.services.jwt import JwtService


class TestJWTTokenRefreshAPI(TestCase):
    async def test_token_refresh_success(self):
        # 카카오 로그인이 아직 없으므로 회원을 직접 만들고 토큰을 발급합니다.
        user = await User.create(kakao_id="kakao-refresh-test", nickname="리프레시테스터")
        tokens = JwtService().issue_jwt_pair(user)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            client.cookies["refresh_token"] = str(tokens["refresh_token"])
            response = await client.get("/api/v1/auth/token/refresh")

        assert response.status_code == status.HTTP_200_OK
        access_token = response.json()["access_token"]
        verified = JwtService().verify_jwt(token=access_token, token_type="access")
        assert verified.payload["user_id"] == user.id

    async def test_token_refresh_missing_token(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/auth/token/refresh")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert response.json()["detail"] == "Refresh token is missing."
