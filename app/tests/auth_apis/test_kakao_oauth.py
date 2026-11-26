"""카카오 클라이언트·닉네임 규칙 단위 테스트 (DB·실제 카카오 호출 없음)."""

import httpx
import pytest

from app.core import config
from app.core.exceptions import AppError
from app.services.auth_service import nickname_base, nickname_with_suffix
from app.services.kakao_oauth import KAKAO_TOKEN_URL, KakaoOAuthClient, parse_kakao_user

USER_ME = {
    "id": 123456789,
    "kakao_account": {
        "profile": {"nickname": "다올이"},
        "email": "daol@example.com",
        "is_email_valid": True,
        "is_email_verified": True,
    },
}


def make_client(handler) -> KakaoOAuthClient:
    return KakaoOAuthClient(http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)))


async def test_fetch_user_sends_client_secret(monkeypatch):
    monkeypatch.setattr(config, "KAKAO_REST_API_KEY", "rest-key")
    monkeypatch.setattr(config, "KAKAO_CLIENT_SECRET", "secret")
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if str(request.url) == KAKAO_TOKEN_URL:
            seen["form"] = request.content.decode()
            return httpx.Response(200, json={"access_token": "kakao-at"})
        seen["auth"] = request.headers["Authorization"]
        return httpx.Response(200, json=USER_ME)

    user = await make_client(handler).fetch_user("the-code")

    assert user.kakao_id == "123456789"
    assert user.nickname == "다올이"
    assert user.email == "daol@example.com"
    assert "client_secret=secret" in seen["form"]
    assert "client_id=rest-key" in seen["form"]
    assert "code=the-code" in seen["form"]
    assert seen["auth"] == "Bearer kakao-at"


@pytest.mark.parametrize(
    ("status_code", "expected_code"),
    [(400, "KAKAO_AUTH_FAILED"), (401, "KAKAO_AUTH_FAILED"), (500, "EXTERNAL_API_ERROR")],
)
async def test_token_error_mapping(status_code, expected_code):
    client = make_client(lambda request: httpx.Response(status_code, json={"error": "invalid_grant"}))
    with pytest.raises(AppError) as exc:
        await client.fetch_user("bad")
    assert exc.value.code == expected_code


async def test_timeout_is_external_error():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("timeout", request=request)

    with pytest.raises(AppError) as exc:
        await make_client(handler).fetch_user("code")
    assert exc.value.code == "EXTERNAL_API_ERROR"
    assert exc.value.status_code == 502


def test_email_ignored_when_not_verified():
    data = {"id": 1, "kakao_account": {"email": "x@example.com", "is_email_valid": True, "is_email_verified": False}}
    assert parse_kakao_user(data).email is None


def test_email_none_when_not_agreed():
    assert parse_kakao_user({"id": 1, "kakao_account": {"profile": {"nickname": "a"}}}).email is None


def test_missing_id_is_auth_failed():
    with pytest.raises(AppError) as exc:
        parse_kakao_user({"kakao_account": {}})
    assert exc.value.code == "KAKAO_AUTH_FAILED"


@pytest.mark.parametrize(
    ("base", "expected"),
    [
        ("다올이", "다올이a1b2"),  # 3 + 4 = 7자
        ("여섯글자닉네", "여섯글자닉네a1b2"),  # 6 + 4 = 10자
        ("일곱글자닉네임", "일곱글자닉네a1b2"),  # 11자가 되므로 앞 6자 + 4자리
        ("가", "가a1b2"),
    ],
)
def test_nickname_with_suffix(base, expected):
    assert nickname_with_suffix(base, "a1b2") == expected


def test_nickname_base():
    assert nickname_base(None) == "다올이"
    assert nickname_base("   ") == "다올이"
    assert nickname_base("열한글자가넘는긴닉네임이야") == "열한글자가넘는긴닉네"
