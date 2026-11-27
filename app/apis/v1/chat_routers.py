"""챗봇 API (명세 7-4 ~ 7-6). 담당: 유정

가짜 응답 브랜치(`feat/guide-chat-mock`)를 dev에 합칠 때 이 파일이 겹치면 그 브랜치 쪽 내용을 그대로 쓰면 됩니다.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.apis.v1.stubs import not_implemented
from app.dependencies.security import get_request_user
from app.models.users import User

chat_router = APIRouter(prefix="/chat", tags=["chat"])


@chat_router.get("/suggestions", status_code=status.HTTP_200_OK)
async def get_suggestions(_user: Annotated[User, Depends(get_request_user)]):
    """7-4 추천 질문 3개 (CHAT-001, F-1)"""
    return not_implemented()


@chat_router.post("/sessions", status_code=status.HTTP_201_CREATED)
async def create_session(_user: Annotated[User, Depends(get_request_user)]):
    """7-5 채팅창을 열 때 새 대화 만들기 (CHAT-001, F-1)"""
    return not_implemented()


@chat_router.post("/sessions/{session_id}/messages", status_code=status.HTTP_200_OK)
async def send_message(session_id: int, _user: Annotated[User, Depends(get_request_user)]):
    """7-6 질문 보내기 → 답변 SSE (CHAT-001·002·004·005, VERI-004, F-1)"""
    return not_implemented()
