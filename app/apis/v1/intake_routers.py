"""복용 기록 API (명세 4장). 담당: 민정"""

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from app.apis.v1.stubs import not_implemented
from app.dependencies.security import get_request_user
from app.models.users import User

intake_router = APIRouter(prefix="/intakes", tags=["intakes"])


@intake_router.get("", status_code=status.HTTP_200_OK)
async def get_daily_intakes(
    _user: Annotated[User, Depends(get_request_user)],
    target_date: Annotated[date | None, Query(alias="date")] = None,
):
    """날짜별 복용 기록, 최근 3일 (MED-005, A-2)"""
    return not_implemented()


@intake_router.patch("/{intake_id}", status_code=status.HTTP_200_OK)
async def update_intake(intake_id: int, _user: Annotated[User, Depends(get_request_user)]):
    """복용 체크·취소 + 꽃 결과 (MED-005·017, A-2)"""
    return not_implemented()
