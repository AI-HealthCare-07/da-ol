"""회원 API (명세 4장). 명세 담당: 민정 / 구현: `POST /profile`은 민정, 나머지 셋은 설아(11/23)."""

from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.apis.v1.stubs import not_implemented
from app.dependencies.security import get_request_user
from app.models.users import User

user_router = APIRouter(prefix="/users/me", tags=["users"])


@user_router.get("", status_code=status.HTTP_200_OK)
async def get_me(_user: Annotated[User, Depends(get_request_user)]):
    """내 정보 (USER-008, E-1). 구현: 설아"""
    return not_implemented()


@user_router.post("/profile", status_code=status.HTTP_200_OK)
async def complete_profile(_user: Annotated[User, Depends(get_request_user)]):
    """추가 정보 입력 + 필수 약관 동의 (USER-002, A-1). 구현: 민정"""
    return not_implemented()


@user_router.get("/health-profile", status_code=status.HTTP_200_OK)
async def get_health_profile(_user: Annotated[User, Depends(get_request_user)]):
    """건강 프로필 조회 (USER-010, E-2). 구현: 설아"""
    return not_implemented()


@user_router.put("/health-profile", status_code=status.HTTP_200_OK)
async def put_health_profile(_user: Annotated[User, Depends(get_request_user)]):
    """건강 프로필 저장, 기저질환 포함 (USER-010, E-2). 구현: 설아"""
    return not_implemented()
