"""clova_ocr.py 테스트. 실제 CLOVA는 부르지 않고 fixture와 httpx.MockTransport로 확인합니다.

fixture(app/tests/fixtures/clova/)는 공식 문서의 V2 응답 형식에 맞춰 PR #24 테스트 처방 이미지를 본떠 만든 것입니다.
실제 CLOVA 응답으로 확인하는 테스트는 test_clova_real.py에 있습니다(README.md 참고).
"""

import asyncio
import base64
import copy
import json
from pathlib import Path

import httpx
import pytest

import app.services.scan_service as sp
from app.core.config import Config
from app.dtos.scan import DocumentStatus, FailReason
from app.services.clova_ocr import ClovaOcrClient, ClovaOcrError, parse_clova_response
from app.tests.test_scan_service import make_deps

FIXTURES = Path(__file__).parent / "fixtures" / "clova"
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16
JPG = b"\xff\xd8\xff\xe0" + b"\x00" * 16
URL = "https://example.apigw.ntruss.com/custom/v1/0000/fixture/general"
SECRET = "test-secret"


def run(coro):
    return asyncio.run(coro)


def load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def texts(data: dict) -> list[str]:
    return [line.text for line in parse_clova_response(data)]


# ---------------------------------------------------------------------------
# 응답 → 줄
# ---------------------------------------------------------------------------
def test_table_row_becomes_one_line():
    assert texts(load("case04_table.json")) == [
        "처 방 전 (Case 04 - 정상)",
        "교부번호: 2026-1124-004 | 처방일: 2026-11-24",
        "의료기관: 논공이비인후과 | 환자성명: [비식별 샘플]",
        "의약품명 1회 투약량 1일 횟수 총 일수 용법",
        "코대원포르테시럽 20mL 3회 3일 식후 30분",
        "펠루비정 1정 3회 3일 식후 30분",
        "무코스타정 1정 3회 3일 식후 30분",
    ]


def test_table_text_in_fields_is_not_duplicated():
    # CLOVA는 표 안 글자를 fields에도 같이 줍니다. 표 행으로 한 번만 나와야 합니다.
    lines = texts(load("case04_table.json"))
    assert sum("펠루비정" in t for t in lines) == 1


def test_fields_only_groups_by_line_break():
    # 표 인식이 없을 때(enableTableDetection 꺼짐·표를 못 찾음)도 화면 한 줄 = 한 줄
    assert texts(load("case04_fields_only.json")) == texts(load("case04_table.json"))


def test_fields_without_line_break_split_by_position():
    # lineBreak가 빠진 응답(V1 등)은 세로 위치로 줄을 나눕니다
    data = load("case04_fields_only.json")
    for f in data["images"][0]["fields"]:
        f.pop("lineBreak", None)
    assert texts(data) == texts(load("case04_table.json"))


def test_wrapped_cell_text_joined_in_row():
    # 칸 안에서 줄바꿈된 글자('아침 식후 30' / '분', '아스피린프로텍트정' / '100mg')가 한 줄로 이어짐
    lines = texts(load("case07_wrapped_cells.json"))
    assert "노바스크정 5mg 1정 1회 30일 아침 식후 30 분" in lines
    assert "아스피린프로텍트정 100mg 1정 1회 30일 아침 식후 30 분" in lines
    assert "다이아벡스정 500mg 1정 2회 30일 아침·저녁 식 후 즉시" in lines


def test_word_confidence_kept():
    # 흐린 마지막 줄(Case 10)의 낮은 신뢰도가 단어마다 그대로 남아야 needs_check가 켜짐
    line = parse_clova_response(load("case10_low_confidence.json"))[-1]
    assert line.text == "가스모틴정 5mg 1정 3회 30일 식후 30분"
    assert [w.confidence for w in line.words] == [0.62, 0.48, 0.51, 0.57, 0.6, 0.58, 0.52]
    assert all(
        w.confidence >= 0.98 for ln in parse_clova_response(load("case10_low_confidence.json"))[3:6] for w in ln.words
    )


def test_pill_envelope_rows_and_shared_instruction():
    # 약봉투(Case 11): 빈 행은 건너뛰고, 표 아래 공통 복약안내는 표 행 다음 줄로
    lines = texts(load("case11_pill_envelope.json"))
    i = lines.index("세토펜정 325mg 1정 3회 3일")
    assert lines[i + 1] == "베아제정 1정 3회 3일"
    assert lines[i + 2] == "복약안내 아침 점심 저녁 / 식사 후 30분 복용"
    assert "" not in lines


def test_line_numbers_and_word_positions():
    lines = parse_clova_response(load("case07_wrapped_cells.json"))
    assert [ln.line_idx for ln in lines] == list(range(len(lines)))
    assert all(ln.page_no == 0 for ln in lines)  # page_no는 run_scan_job이 채움
    for ln in lines:
        assert all(ln.text[w.start : w.end] == w.text for w in ln.words)


def test_confidence_clamped_and_blank_words_dropped():
    data = load("case04_table.json")
    cell = data["images"][0]["tables"][0]["cells"][5]  # 코대원포르테시럽 칸
    words = cell["cellTextLines"][0]["cellWords"]
    words[0]["inferConfidence"] = 1.2
    words.append({"inferText": "  ", "inferConfidence": 0.9})
    line = parse_clova_response(data)[4]
    assert line.words[0].confidence == 1.0
    assert line.text == "코대원포르테시럽 20mL 3회 3일 식후 30분"


def test_infer_failure_raises():
    with pytest.raises(ClovaOcrError, match="FAILURE"):
        parse_clova_response(load("infer_failure.json"))
    with pytest.raises(ClovaOcrError):
        parse_clova_response({"images": []})


def test_no_text_fixture_is_no_text():
    assert sp.is_no_text(parse_clova_response(load("no_text.json")))
    assert not sp.is_no_text(parse_clova_response(load("case04_table.json")))


def test_masking_after_parse():
    # 줄로 묶은 뒤 가리기(run_scan_job ②)가 연락처를 잡는지
    lines = [sp.mask_line(ln) for ln in parse_clova_response(load("case11_pill_envelope.json"))]
    assert "TEL: [연락처]" in [ln.text for ln in lines]


# ---------------------------------------------------------------------------
# 클라이언트
# ---------------------------------------------------------------------------
def client_with(handler) -> ClovaOcrClient:
    http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return ClovaOcrClient(URL, SECRET, http_client=http)


def test_request_shape():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["secret"] = request.headers.get("X-OCR-SECRET")
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json=load("case04_table.json"))

    lines = run(client_with(handler).read_page(PNG))
    body = seen["body"]
    assert seen["url"] == URL and seen["secret"] == SECRET
    assert body["version"] == "V2" and body["lang"] == "ko" and body["enableTableDetection"] is True
    assert body["requestId"] and isinstance(body["timestamp"], int)
    assert body["images"][0]["format"] == "png"
    assert base64.b64decode(body["images"][0]["data"]) == PNG
    assert len(lines) == 7


def test_jpg_format_and_unknown_bytes():
    client = ClovaOcrClient(URL, SECRET, http_client=httpx.AsyncClient())
    assert client.build_request_body(JPG)["images"][0]["format"] == "jpg"
    with pytest.raises(ClovaOcrError):
        client.build_request_body(b"%PDF-1.7")  # PDF는 업로드 단계에서 페이지 이미지로 바꿔서 보냄


@pytest.mark.parametrize(
    "response, expected",
    [
        (httpx.Response(500, json={"code": "0500", "message": "Internal Server Error"}), r"HTTP 500 \(code=0500\)"),
        (httpx.Response(401, text="unauthorized"), "HTTP 401"),
        (httpx.Response(200, text="not json"), "JSON"),
        (httpx.Response(200, json=load("infer_failure.json")), "FAILURE"),
    ],
)
def test_error_responses(response, expected):
    with pytest.raises(ClovaOcrError, match=expected) as e:
        run(client_with(lambda request: response).read_page(PNG))
    assert SECRET not in str(e.value)


def test_network_error_message_has_no_details():
    def handler(request):
        raise httpx.ConnectTimeout(f"timed out {URL}", request=request)

    with pytest.raises(ClovaOcrError) as e:
        run(client_with(handler).read_page(PNG))
    assert str(e.value) == "CLOVA 호출 실패: ConnectTimeout"


def test_error_message_has_no_ocr_text():
    # 인식 글자는 가리기 전 원문이라 예외 메시지에 들어가면 안 됨
    data = load("case11_pill_envelope.json")
    data["images"][0]["inferResult"] = "ERROR"
    with pytest.raises(ClovaOcrError) as e:
        run(client_with(lambda request: httpx.Response(200, json=data)).read_page(PNG))
    assert "053" not in str(e.value) and "김" not in str(e.value)


def test_requires_url_and_secret():
    with pytest.raises(ValueError):
        ClovaOcrClient.from_config(Config(CLOVA_OCR_URL="", CLOVA_OCR_SECRET=""))
    run(ClovaOcrClient.from_config(Config(CLOVA_OCR_URL=URL, CLOVA_OCR_SECRET=SECRET)).aclose())


# ---------------------------------------------------------------------------
# run_scan_job에 끼워서 끝까지
# ---------------------------------------------------------------------------
def deps_with_clova(handler):
    deps = make_deps(ocr=client_with(handler))

    async def page_images(scan_id):
        return [(1, PNG)]

    deps.repo.page_images = page_images
    return deps


def test_job_with_clova_client():
    deps = deps_with_clova(lambda request: httpx.Response(200, json=load("case04_table.json")))
    run(sp.run_scan_job(deps, 42))
    assert deps.repo.doc.status == DocumentStatus.OCR_DONE
    saved = deps.repo.lines  # 가린 줄(save_masked_lines)
    assert saved[4]["page_no"] == 1
    assert [w[0] for w in saved[4]["words"]] == ["코대원포르테시럽", "20mL", "3회", "3일", "식후", "30분"]


def test_job_clova_failure_retries_then_ocr_error():
    calls = []

    def handler(request):
        calls.append(1)
        return httpx.Response(200, json=load("infer_failure.json"))

    deps = deps_with_clova(handler)
    run(sp.run_scan_job(deps, 42))
    assert deps.repo.doc.fail_reason == FailReason.OCR_ERROR
    assert len(calls) == sp.OCR_MAX_RETRY + 1


def test_job_clova_blank_photo_is_no_text():
    deps = deps_with_clova(lambda request: httpx.Response(200, json=load("no_text.json")))
    run(sp.run_scan_job(deps, 42))
    assert deps.repo.doc.fail_reason == FailReason.NO_TEXT


def test_fixture_files_are_independent():
    # load()가 매번 새 dict를 주는지(테스트끼리 fixture를 고쳐도 섞이지 않게)
    a = load("case04_table.json")
    b = copy.deepcopy(a)
    a["images"][0]["fields"].clear()
    assert load("case04_table.json") == b
