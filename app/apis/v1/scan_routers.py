"""처방 등록 API (명세 6장). 담당: 채민

로직은 `app/services/scan_service.py`에 있고, 여기서는 그 함수를 불러 연결합니다.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, UploadFile, status
from starlette.concurrency import run_in_threadpool

from app.apis.v1.stubs import not_implemented
from app.core.exceptions import AppError
from app.dependencies.security import get_request_user
from app.dtos.scan import DocType
from app.models.users import User
from app.services.scan_upload import UploadError, prepare_pages, read_uploads

scan_router = APIRouter(tags=["scans"])


def upload_error(e: UploadError) -> AppError:
    """파일 검사 실패 → 1-1 에러 형식({code, message}). 6-3 상태 코드·문구 그대로."""
    return AppError(e.status_code, e.code, e.message)


@scan_router.post("/scans", status_code=status.HTTP_202_ACCEPTED)
async def upload_scan(
    _user: Annotated[User, Depends(get_request_user)],
    files: Annotated[list[UploadFile], File(description="jpg·png·pdf, 1개 10MB·합계 30MB, 올린 순서대로 페이지 번호")],
    doc_type: Annotated[DocType, Form(description="prescription(처방전) / pill_envelope(약봉투)")],
):
    """처방전·약봉투 파일 업로드 → 읽기 시작 (OCR-001·002, B-1)

    파일 크기·형식·암호·손상·페이지 수 검사는 요청을 받을 때 끝내고(6장 비고), 통과한 경우에만 202를 돌려줍니다.
    """
    try:
        uploaded = await read_uploads(files)
        # PDF 그리기는 무거운 일반 함수라 스레드에서 돌림. 이벤트 루프에서 바로 부르면 그리는 동안
        # 다른 요청(챗봇 답변 흐름 등)이 모두 멈춤
        pages = await run_in_threadpool(prepare_pages, uploaded)
    except UploadError as e:
        raise upload_error(e) from None  # 파일 내용은 메시지·로그에 남기지 않음

    # TODO(다음 단계): pages·doc_type으로 하루 20회 제한(RATE_LIMITED) 확인 → 문서·페이지 저장
    # (scan_repository·FileStore) → run_scan_job 시작 → 202. 그 전까지 검사를 통과하면 501
    del pages, doc_type
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
