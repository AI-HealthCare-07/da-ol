"""공용 에러 응답 (명세 1-1): AppError · 422 VALIDATION_ERROR · 400 · 404/405 · 500. DB 없이 작은 앱으로 확인합니다."""

from datetime import date

import pytest
from fastapi import FastAPI, Form
from httpx import ASGITransport, AsyncClient
from pydantic import BaseModel, Field
from starlette import status

from app.core.exceptions import AppError, ErrorCode, field_key, register_exception_handlers


class Dose(BaseModel):
    timing: str


class Drug(BaseModel):
    drug_name: str = Field(min_length=1, max_length=5)
    total_days: int = Field(ge=1, le=365)
    doses: list[Dose] = []


class Body(BaseModel):
    nickname: str = Field(min_length=2)
    birth_date: date
    drugs: list[Drug] = []
    flag: bool = False


app = FastAPI()
register_exception_handlers(app)


@app.post("/items")
async def create_item(body: Body) -> dict:
    return {"ok": True}


@app.get("/boom")
async def boom() -> dict:
    raise AppError(status.HTTP_404_NOT_FOUND, ErrorCode.NOT_FOUND, "처방을 찾을 수 없어요", extra={"hint": 1})


@app.post("/upload")
async def upload(name: str = Form(...)) -> dict:
    return {"ok": True}


@app.get("/crash")
async def crash() -> dict:
    raise RuntimeError("일부러 터뜨리는 에러")


async def post(json: dict) -> dict:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/items", json=json)
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    body = response.json()
    assert body["code"] == "VALIDATION_ERROR"
    assert body["message"] == "입력한 내용을 확인해 주세요"
    return body["fields"]


async def test_missing_and_too_short():
    fields = await post({"nickname": "a"})
    assert fields == {"nickname": "2자 이상 입력해 주세요", "birth_date": "필수 항목이에요"}


async def test_list_item_uses_brackets():
    fields = await post(
        {
            "nickname": "다올이",
            "birth_date": "1958-03-14",
            "drugs": [
                {"drug_name": "타이레놀", "total_days": 3},
                {"drug_name": "아주긴약이름입니다", "total_days": 0, "doses": [{}]},
            ],
        }
    )
    assert fields == {
        "drugs[1].drug_name": "5자 이하로 입력해 주세요",
        "drugs[1].total_days": "1 이상으로 입력해 주세요",
        "drugs[1].doses[0].timing": "필수 항목이에요",
    }


async def test_unknown_error_type_uses_default_message():
    # bool 칸에 목록 → bool_type. FIELD_MESSAGES 표에 없는 종류라 기본 문구
    fields = await post({"nickname": "다올이", "birth_date": "1958-03-14", "flag": [1]})
    assert fields == {"flag": "형식이 맞지 않아요"}


async def test_broken_json_body():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/items", content=b'{"drugs": [', headers={"Content-Type": "application/json"})
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    body = response.json()
    assert body["code"] == "VALIDATION_ERROR"
    assert body["fields"] == {"body": "요청 형식이 맞지 않아요"}  # 글자 위치("[11]")가 칸 이름으로 나가지 않게


async def test_broken_multipart_body_is_400_validation_error():
    # Content-Disposition 없는 조각 → FastAPI가 본문을 못 읽어 400. 깨진 JSON과 같은 모양으로
    broken = b"--x\r\nContent-Type: text/plain\r\n\r\nabc\r\n--x--\r\n"
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/upload", content=broken, headers={"Content-Type": "multipart/form-data; boundary=x"}
        )
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.json() == {
        "code": "VALIDATION_ERROR",
        "message": "입력한 내용을 확인해 주세요",
        "fields": {"body": "요청 형식이 맞지 않아요"},
    }


async def test_unknown_path_is_not_found():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/nope")
    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response.json() == {"code": "NOT_FOUND", "message": "요청한 주소를 찾을 수 없어요"}


async def test_wrong_method_is_method_not_allowed():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/items")  # POST만 있음
    assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED
    assert response.json() == {"code": "METHOD_NOT_ALLOWED", "message": "지원하지 않는 요청 방식이에요"}
    assert response.headers["allow"] == "POST"


async def test_unhandled_error_is_internal_error():
    # raise_app_exceptions=False: 테스트 클라이언트가 서버 에러를 다시 던지지 않고 응답을 받게
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/crash")
    assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    assert response.json() == {"code": "INTERNAL_ERROR", "message": "잠시 후 다시 시도해 주세요"}


async def test_app_error_response():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/boom")
    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response.json() == {"code": "NOT_FOUND", "message": "처방을 찾을 수 없어요", "hint": 1}


@pytest.mark.parametrize(
    ("loc", "expected"),
    [
        (("body", "birth_date"), "birth_date"),
        (("body", "drugs", 0, "dose_per_time"), "drugs[0].dose_per_time"),
        (("body", "drugs", 1, "dosage", "doses", 0, "timing"), "drugs[1].dosage.doses[0].timing"),
        (("query", "date"), "date"),
        (("body",), "body"),
    ],
)
def test_field_key(loc, expected):
    assert field_key(loc) == expected
