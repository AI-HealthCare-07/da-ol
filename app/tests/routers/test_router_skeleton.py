"""라우터 뼈대: 명세 3장 1차 API 28개가 모두 등록돼 있고, 로그인 없이 부르면 401인지 확인합니다."""

import pytest
from fastapi.routing import APIRoute
from httpx import ASGITransport, AsyncClient
from starlette import status

from app.main import app

# 명세 3장 1차 API 목록 (경로 앞 /api/v1 생략)
SPEC_ROUTES = {
    ("POST", "/auth/kakao"),
    ("POST", "/auth/refresh"),
    ("POST", "/auth/logout"),
    ("GET", "/users/me"),
    ("POST", "/users/me/profile"),
    ("GET", "/users/me/health-profile"),
    ("PUT", "/users/me/health-profile"),
    ("GET", "/intakes"),
    ("PATCH", "/intakes/{intake_id}"),
    ("POST", "/prescriptions"),
    ("GET", "/home"),
    ("GET", "/prescription-items/{prescription_item_id}"),
    ("GET", "/prescriptions"),
    ("GET", "/prescriptions/{prescription_id}"),
    ("POST", "/scans"),
    ("GET", "/scans/{scan_id}"),
    ("PATCH", "/scans/{scan_id}"),
    ("GET", "/scans/{scan_id}/pages/{page_no}/image"),
    ("POST", "/scans/{scan_id}/confirm"),
    ("DELETE", "/scans/{scan_id}"),
    ("GET", "/drugs"),
    ("PATCH", "/dose-conditions/{condition_id}"),
    ("GET", "/prescriptions/{prescription_id}/guides"),
    ("POST", "/prescriptions/{prescription_id}/guides/retry"),
    ("GET", "/guides"),
    ("GET", "/chat/suggestions"),
    ("POST", "/chat/sessions"),
    ("POST", "/chat/sessions/{session_id}/messages"),
}

PUBLIC_ROUTES = {("POST", "/auth/kakao"), ("POST", "/auth/refresh")}


def registered_routes() -> set[tuple[str, str]]:
    routes = set()
    for route in app.routes:
        if isinstance(route, APIRoute) and route.path.startswith("/api/v1"):
            for method in route.methods:
                routes.add((method, route.path.removeprefix("/api/v1")))
    return routes


def test_all_spec_routes_registered() -> None:
    assert registered_routes() == SPEC_ROUTES


@pytest.mark.asyncio
@pytest.mark.parametrize(("method", "path"), sorted(SPEC_ROUTES - PUBLIC_ROUTES))
async def test_routes_require_login(method: str, path: str) -> None:
    url = "/api/v1" + path.format(
        intake_id=1, prescription_item_id=1, prescription_id=1, scan_id=1, page_no=1, condition_id=1, session_id=1
    )
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.request(method, url, params={"q": "타이레놀"} if path == "/drugs" else None)
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
