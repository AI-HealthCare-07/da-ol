"""약 검색 API (명세 6장). 담당: 채민"""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from app.apis.v1.stubs import not_implemented
from app.dependencies.security import get_request_user
from app.models.users import User

drug_router = APIRouter(prefix="/drugs", tags=["drugs"])


@drug_router.get("", status_code=status.HTTP_200_OK)
async def search_drugs(
    _user: Annotated[User, Depends(get_request_user)],
    q: Annotated[str, Query(min_length=1)],
    limit: Annotated[int, Query(ge=1, le=20)] = 10,
):
    """약 검색. OCR 매칭 후보는 `limit=3`, 직접 입력 검색은 기본 10 (OCR-005, MED-001, B-1·B-2)"""
    return not_implemented()
