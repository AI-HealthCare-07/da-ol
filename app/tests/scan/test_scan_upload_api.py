"""POST /scans 라우터: 파일 검사 실패를 1-1 에러 형식({code, message})으로 돌려주는지 확인합니다.

DB를 쓰지 않아서 TestCase 없이 async 함수로 씁니다(pytest asyncio_mode=auto).
성공했을 때 문서 저장·읽기 시작은 아직 연결 전이라 501(NOT_IMPLEMENTED)입니다.
"""

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.exceptions import ErrorCode
from app.dependencies.security import get_request_user
from app.main import app
from app.models.users import User
from app.services import scan_upload as su
from app.tests.scan.test_scan_upload import ENCRYPTED_PDF, image_bytes, pdf_bytes

URL = "/api/v1/scans"


@pytest.fixture(autouse=True)
def logged_in():
    app.dependency_overrides[get_request_user] = lambda: User(id=1)
    yield
    app.dependency_overrides.pop(get_request_user, None)


async def upload(files: list[tuple[str, bytes]], doc_type: str | None = "prescription"):
    data = {"doc_type": doc_type} if doc_type else {}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        return await client.post(URL, files=[("files", (name, body)) for name, body in files], data=data)


@pytest.mark.parametrize(
    "files, status_code, code",
    [
        ([("a.gif", b"GIF89a....")], 415, "UNSUPPORTED_FILE_TYPE"),
        ([("a.jpg", image_bytes()), ("secret.pdf", ENCRYPTED_PDF)], 422, "ENCRYPTED_PDF"),
        ([("broken.pdf", b"%PDF-1.4 broken")], 422, "INVALID_FILE"),
        ([("many.pdf", pdf_bytes(su.MAX_PAGES + 1))], 422, "TOO_MANY_PAGES"),
    ],
)
async def test_upload_errors_use_error_format(files, status_code, code):
    response = await upload(files)
    assert response.status_code == status_code
    body = response.json()
    assert body["code"] == code
    assert body["message"] == su.MESSAGES[ErrorCode(code)]
    assert set(body) == {"code", "message"}  # 파일 내용·이름은 응답에 넣지 않음


async def test_file_too_large(monkeypatch):
    monkeypatch.setattr(su, "MAX_FILE_BYTES", 100)
    response = await upload([("big.jpg", b"\xff\xd8\xff" + b"0" * 200)])
    assert response.status_code == 413 and response.json()["code"] == "FILE_TOO_LARGE"


@pytest.mark.parametrize(
    "files, doc_type, field",
    [
        ([("a.png", None)], None, "doc_type"),  # doc_type 없음
        ([("a.png", None)], "receipt", "doc_type"),  # 고를 수 없는 값
        ([], "prescription", "files"),  # 파일 없음
    ],
)
async def test_missing_or_wrong_fields_are_validation_error(files, doc_type, field):
    files = [(name, image_bytes()) for name, _ in files]
    data = {"doc_type": doc_type} if doc_type else {}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(URL, files=[("files", f) for f in files] or None, data=data)
    assert response.status_code == 422
    body = response.json()
    assert body["code"] == ErrorCode.VALIDATION_ERROR
    assert field in body["fields"]  # 프론트가 이 칸 아래에 문구를 띄움


async def test_valid_upload_not_connected_yet():
    # 검사는 통과. 문서 저장·읽기 시작은 다음 단계라 아직 501
    response = await upload([("a.jpg", image_bytes("JPEG")), ("b.pdf", pdf_bytes(2))])
    assert response.status_code == 501 and response.json()["code"] == "NOT_IMPLEMENTED"


async def test_requires_login():
    app.dependency_overrides.pop(get_request_user, None)
    response = await upload([("a.png", image_bytes())])
    assert response.status_code == 401
