"""가이드 API (명세 7-1 ~ 7-3). 담당: 유정

가짜 응답 브랜치(`feat/guide-chat-mock`)를 dev에 합칠 때 이 파일이 겹치면 그 브랜치 쪽 내용을 그대로 쓰면 됩니다.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.apis.v1.stubs import not_implemented
from app.dependencies.security import get_request_user
from app.models.users import User

guide_router = APIRouter(tags=["guides"])


@guide_router.get("/prescriptions/{prescription_id}/guides", status_code=status.HTTP_200_OK)
async def get_prescription_guides(prescription_id: int, _user: Annotated[User, Depends(get_request_user)]):
    """7-1 복약·생활습관 가이드 보기, 만드는 중이면 진행 상태 (GUIDE-001·002·004·006·007, D-2·C-1)"""
    return not_implemented()


@guide_router.post("/prescriptions/{prescription_id}/guides/retry", status_code=status.HTTP_202_ACCEPTED)
async def retry_prescription_guides(prescription_id: int, _user: Annotated[User, Depends(get_request_user)]):
    """7-2 실패 화면의 [다시 시도] (GUIDE-007, D-2)"""
    return not_implemented()


@guide_router.get("/guides", status_code=status.HTTP_200_OK)
async def list_guides(_user: Annotated[User, Depends(get_request_user)]):
    """7-3 내 가이드 목록 (GUIDE-004, D-1)"""
    return not_implemented()
