"""홈 API (명세 5장). 담당: 설아"""

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from app.apis.v1.stubs import not_implemented
from app.dependencies.security import get_request_user
from app.models.users import User

home_router = APIRouter(prefix="/home", tags=["home"])


@home_router.get("", status_code=status.HTTP_200_OK)
async def get_home(
    _user: Annotated[User, Depends(get_request_user)],
    target_date: Annotated[date | None, Query(alias="date")] = None,
):
    """날짜별 원형 약통 화면 데이터 (MED-005·008·009·016·017, A-2)"""
    return not_implemented()
