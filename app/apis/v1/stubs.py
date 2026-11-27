"""라우터 뼈대용 임시 응답. 아직 만들지 않은 API는 501과 명세 1-1 형식 본문을 돌려줍니다.

구현할 때 `return not_implemented()` 줄을 지우고 실제 코드를 넣으면 됩니다.
모든 API를 구현하면 이 파일도 지웁니다.
"""

from fastapi import status
from fastapi.responses import ORJSONResponse


def not_implemented() -> ORJSONResponse:
    return ORJSONResponse(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        content={"code": "NOT_IMPLEMENTED", "message": "아직 만들지 않은 API예요"},
    )
