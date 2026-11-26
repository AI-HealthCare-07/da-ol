"""7장 가이드 API (가짜 응답). 명세서 7-1 ~ 7-3의 응답 예시를 그대로 돌려줍니다.

- 아직 DB·AI와 연결하지 않았습니다. 프론트가 화면을 먼저 붙일 수 있게 하려는 임시 API예요.
- 로그인 확인도 아직 없습니다(카카오 로그인 PR 뒤에 Depends(get_request_user)를 붙임).
- mock_state는 가짜 응답 전용 값입니다. 실제 구현에서는 지웁니다.
"""

import copy
from typing import Literal

from fastapi import APIRouter, Query, status

from app.apis.v1.examples import guide_chat_examples as examples

guide_router = APIRouter(tags=["guides (가짜 응답)"])

GUIDE_BY_STATE = {
    "completed": examples.GUIDE_COMPLETED,
    "in_progress": examples.GUIDE_IN_PROGRESS,
    "failed": examples.GUIDE_FAILED,
}


@guide_router.get("/prescriptions/{prescription_id}/guides", status_code=status.HTTP_200_OK)
async def get_prescription_guides(
    prescription_id: int,
    mock_state: Literal["completed", "in_progress", "failed"] = Query(
        "completed", description="[가짜 응답 전용] 보고 싶은 상태"
    ),
) -> dict:
    """7-1 처방 하나의 복약·생활습관 가이드."""
    body = copy.deepcopy(GUIDE_BY_STATE[mock_state])
    body["prescription_id"] = prescription_id
    return body


@guide_router.post("/prescriptions/{prescription_id}/guides/retry", status_code=status.HTTP_202_ACCEPTED)
async def retry_prescription_guides(prescription_id: int) -> dict:
    """7-2 실패한 가이드 다시 시도."""
    body = copy.deepcopy(examples.GUIDE_RETRY)
    body["prescription_id"] = prescription_id
    return body


@guide_router.get("/guides", status_code=status.HTTP_200_OK)
async def list_guides(page: int = Query(1, ge=1), size: int = Query(20, ge=1, le=100)) -> dict:
    """7-3 내 가이드 목록."""
    body = copy.deepcopy(examples.GUIDE_LIST)
    body["page"] = page
    body["size"] = size
    return body
