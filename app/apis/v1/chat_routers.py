"""7장 챗봇 API (가짜 응답). 명세서 7-4 ~ 7-6의 응답 예시를 그대로 돌려줍니다.

- 아직 DB·AI와 연결하지 않았습니다. 프론트가 화면을 먼저 붙일 수 있게 하려는 임시 API예요.
- 모든 API에 로그인 확인(Depens(get_request_user))을 붙였습니다. 테스트에서는ㄴ 가짜 회원으로 바꿔서 확인합니다.
- mock_case는 가짜 응답 전용 값입니다. 실제 구현에서는 지웁니다.
"""

import asyncio
import json
from collections.abc import AsyncIterator
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.apis.v1.examples import guide_chat_examples as examples
from app.dependencies.security import get_request_user
from app.models.users import User

chat_router = APIRouter(prefix="/chat", tags=["chat (가짜 응답)"])


class ChatMessageRequest(BaseModel):
    content: str = Field(min_length=1, max_length=500)
    is_recommended_question: bool = False


def sse(event: str, data: dict) -> str:
    """SSE 한 덩어리: 'event: 이름' 줄, 'data: JSON' 줄, 빈 줄."""
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@chat_router.get("/suggestions", status_code=status.HTTP_200_OK)
async def get_suggestions(_user: Annotated[User, Depends(get_request_user)]) -> dict:
    """7-4 추천 질문 3개."""
    return examples.CHAT_SUGGESTIONS


@chat_router.post("/sessions", status_code=status.HTTP_201_CREATED)
async def create_session(_user: Annotated[User, Depends(get_request_user)]) -> dict:
    """7-5 새 대화방."""
    return examples.CHAT_SESSION


@chat_router.post("/sessions/{session_id}/messages")
async def send_message(
    session_id: int,
    request: ChatMessageRequest,
    _user: Annotated[User, Depends(get_request_user)],
    mock_case: Literal["normal", "physical", "self_harm", "out_of_scope", "error"] = Query(
        "normal", description="[가짜 응답 전용] 보고 싶은 상황"
    ),
) -> StreamingResponse:
    """7-6 질문 보내기. 답변을 SSE(text/event-stream)로 조금씩 내려줍니다."""

    async def events() -> AsyncIterator[str]:
        yield sse("meta", {"user_message_id": 811, "masked_content": request.content})
        for event, data in examples.CHAT_EVENTS[mock_case]:
            await asyncio.sleep(0.3)  # 진짜처럼 조금씩 오게
            yield sse(event, data)
        if mock_case != "error":
            yield sse("done", {"message_id": 812, "show_profile_link": False})

    return StreamingResponse(events(), media_type="text/event-stream")
