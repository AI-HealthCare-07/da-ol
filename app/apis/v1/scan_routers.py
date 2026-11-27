"""처방 등록 API (명세 6장). 담당: 채민

로직은 `app/services/scan_service.py`에 있고, 여기서는 그 함수를 불러 연결합니다.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.apis.v1.stubs import not_implemented
from app.dependencies.security import get_request_user
from app.models.users import User

scan_router = APIRouter(tags=["scans"])


@scan_router.post("/scans", status_code=status.HTTP_202_ACCEPTED)
async def upload_scan(_user: Annotated[User, Depends(get_request_user)]):
    """처방전·약봉투 파일 업로드 → 읽기 시작 (OCR-001·002, B-1)"""
    return not_implemented()


@scan_router.get("/scans/{scan_id}", status_code=status.HTTP_200_OK)
async def get_scan(scan_id: int, _user: Annotated[User, Depends(get_request_user)]):
    """진행 상태 또는 인식 결과 (OCR-002·003·004, B-1·B-2)"""
    return not_implemented()


@scan_router.patch("/scans/{scan_id}", status_code=status.HTTP_200_OK)
async def update_scan(scan_id: int, _user: Annotated[User, Depends(get_request_user)]):
    """인식 결과 수정·문서 종류 다시 고르기, 다시 읽으면 202 (OCR-001·004, B-2)"""
    return not_implemented()


@scan_router.get("/scans/{scan_id}/pages/{page_no}/image", status_code=status.HTTP_200_OK)
async def get_scan_page_image(scan_id: int, page_no: int, _user: Annotated[User, Depends(get_request_user)]):
    """원본 페이지 이미지, `Cache-Control: no-store` (OCR-004, B-2)"""
    return not_implemented()


@scan_router.post("/scans/{scan_id}/confirm", status_code=status.HTTP_201_CREATED)
async def confirm_scan(scan_id: int, _user: Annotated[User, Depends(get_request_user)]):
    """확정 → `create_prescription()` → 원본 삭제 (OCR-004, B-2)"""
    return not_implemented()


@scan_router.delete("/scans/{scan_id}", status_code=status.HTTP_204_NO_CONTENT)
async def cancel_scan(scan_id: int, _user: Annotated[User, Depends(get_request_user)]):
    """읽는 중 취소 → 작업 중단·원본 바로 삭제 (OCR-002, NFR-004, B-1·B-2)"""
    return not_implemented()


@scan_router.patch("/dose-conditions/{condition_id}", status_code=status.HTTP_200_OK)
async def update_dose_condition(condition_id: int, _user: Annotated[User, Depends(get_request_user)]):
    """'복용 조건 확인 필요' 항목을 회원이 고름 (MED-008, B-2)"""
    return not_implemented()
