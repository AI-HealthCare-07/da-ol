"""처방·내 약 API (명세 4장 직접 입력, 5장 조회).

담당: `POST /prescriptions`는 민정, 조회 셋은 설아.
가이드(`/prescriptions/{prescription_id}/guides`)는 `guide_routers.py`에 있습니다.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.apis.v1.stubs import not_implemented
from app.dependencies.security import get_request_user
from app.models.users import User

prescription_router = APIRouter(tags=["prescriptions"])


@prescription_router.post("/prescriptions", status_code=status.HTTP_201_CREATED)
async def create_manual_prescription(_user: Annotated[User, Depends(get_request_user)]):
    """처방 직접 입력 → `create_prescription()` (MED-001, B-1). 구현: 민정"""
    return not_implemented()


@prescription_router.get("/prescriptions", status_code=status.HTTP_200_OK)
async def list_prescriptions(_user: Annotated[User, Depends(get_request_user)]):
    """처방 목록, 복용 중 / 종료 (MED-002, C-1). 구현: 설아"""
    return not_implemented()


@prescription_router.get("/prescriptions/{prescription_id}", status_code=status.HTTP_200_OK)
async def get_prescription(prescription_id: int, _user: Annotated[User, Depends(get_request_user)]):
    """처방 상세: 약·복용 조건·시간표 (MED-002, C-1). 구현: 설아"""
    return not_implemented()


@prescription_router.get("/prescription-items/{prescription_item_id}", status_code=status.HTTP_200_OK)
async def get_prescription_item(prescription_item_id: int, _user: Annotated[User, Depends(get_request_user)]):
    """약 상세: 내 복용 정보 + 공공데이터 (MED-002, OCR-005, C-2). 구현: 설아"""
    return not_implemented()
