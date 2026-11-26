"""7장 가이드·챗봇 가짜 응답 API 테스트. 명세서 7-1 ~ 7-6의 상태 코드와 응답 모양을 확인합니다.

DB를 쓰지 않아서 TestCase 없이 async 함수로 씁니다(pytest asyncio_mode=auto).
"""

import json

from httpx import ASGITransport, AsyncClient
from starlette import status

from app.main import app


def parse_sse(text: str) -> list[tuple[str, dict]]:
    """SSE 글을 (이벤트 이름, data) 목록으로 바꿉니다."""
    events = []
    for block in text.strip().split("\n\n"):
        lines = dict(line.split(": ", 1) for line in block.splitlines())
        events.append((lines["event"], json.loads(lines["data"])))
    return events


async def test_guide_completed():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/prescriptions/555/guides")
    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    assert body["prescription_id"] == 555
    assert body["medication"]["status"] == "completed_with_replacements"
    assert body["disclaimer"]


async def test_guide_in_progress_and_failed_keep_same_keys():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        in_progress = (await client.get("/api/v1/prescriptions/1/guides?mock_state=in_progress")).json()
        failed = (await client.get("/api/v1/prescriptions/1/guides?mock_state=failed")).json()
    for body in (in_progress, failed):
        assert {"is_outdated", "used_default_profile", "disclaimer"} <= body.keys()
    assert failed["medication"]["fallback"]["drugs"]


async def test_retry_and_list():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        retry = await client.post("/api/v1/prescriptions/1/guides/retry")
        guides = await client.get("/api/v1/guides?page=2&size=10")
    assert retry.status_code == status.HTTP_202_ACCEPTED
    assert guides.json()["page"] == 2


async def test_suggestions_and_session():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        suggestions = await client.get("/api/v1/chat/suggestions")
        session = await client.post("/api/v1/chat/sessions")
    assert len(suggestions.json()["questions"]) == 3
    assert session.status_code == status.HTTP_201_CREATED


async def test_message_stream_order():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/v1/chat/sessions/77/messages", json={"content": "같이 먹어도 되나요?"})
    assert response.headers["content-type"].startswith("text/event-stream")
    names = [event for event, _ in parse_sse(response.text)]
    assert names[0] == "meta" and names[-1] == "done"
    assert names[-2] == "sources"


async def test_self_harm_has_no_answer():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/chat/sessions/77/messages?mock_case=self_harm", json={"content": "가상 질문"}
        )
    names = [event for event, _ in parse_sse(response.text)]
    assert names == ["meta", "emergency", "done"]


async def test_empty_question_is_rejected():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/v1/chat/sessions/77/messages", json={"content": ""})
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
