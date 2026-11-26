"""CLOVA General OCR(V2) 클라이언트와 응답 → 줄(OcrLine) 변환 (명세서 6장, 채민)

- ClovaOcrClient는 scan_service.OcrClient를 구현합니다. 재시도·10초 제한은 부르는 쪽(run_scan_job의 _retry)이 맡습니다.
- 응답은 parse_clova_response()로 줄 목록으로 바꿉니다.
  · 표가 있으면 표의 한 행 = 한 줄(칸은 columnIndex 순서). 칸 안에서 줄바꿈된 글자('아침 식후' / '30분')도 한 줄로 이어집니다.
  · 표 밖 글자(fields)는 lineBreak로 줄을 끊고, 위아래로 떨어진 단어는 다른 줄로 나눕니다.
  · 표의 행과 표 밖 줄을 페이지 위에서 아래 순서로 합쳐 line_idx를 0부터 매깁니다.
- page_no는 0으로 두고, 부르는 쪽(run_scan_job)이 replace(line, page_no=...)로 채웁니다.

개인정보: 이 모듈이 돌려주는 글자는 '가리기 전' 원문입니다. 로그·예외 메시지·저장에 글자를 넣지 않습니다.
가리기는 run_scan_job이 줄을 받자마자 mask_lines()으로 합니다.
"""

from __future__ import annotations

import base64
import os
import time
import uuid
from dataclasses import dataclass
from typing import Any

import httpx

from app.services.scan_service import OcrLine, OcrWord, make_line

CLOVA_HTTP_TIMEOUT_SEC = 15  # 연결이 멈췄을 때의 마지막 안전장치. 페이지당 10초 제한은 _retry가 겁니다.


class ClovaOcrError(Exception):
    """CLOVA 호출·응답 오류. 메시지에는 상태 코드·결과 코드만 넣고 인식 글자는 넣지 않습니다."""


# ---------------------------------------------------------------------------
# 응답 → 줄
# ---------------------------------------------------------------------------
@dataclass
class _Box:
    top: float
    bottom: float
    left: float
    right: float

    @property
    def cy(self) -> float:
        return (self.top + self.bottom) / 2

    @property
    def cx(self) -> float:
        return (self.left + self.right) / 2

    @property
    def height(self) -> float:
        return max(self.bottom - self.top, 1.0)

    def contains(self, x: float, y: float) -> bool:
        return self.left <= x <= self.right and self.top <= y <= self.bottom


def _box(obj: dict[str, Any]) -> _Box | None:
    vertices = (obj.get("boundingPoly") or {}).get("vertices") or []
    xs = [float(v.get("x", 0)) for v in vertices]
    ys = [float(v.get("y", 0)) for v in vertices]
    if not xs:
        return None
    return _Box(top=min(ys), bottom=max(ys), left=min(xs), right=max(xs))


def _conf(obj: dict[str, Any]) -> float:
    try:
        c = float(obj.get("inferConfidence", 0.0))
    except (TypeError, ValueError):
        return 0.0
    return min(max(c, 0.0), 1.0)


@dataclass
class _Row:
    top: float
    words: list[OcrWord]


def _table_rows(table: dict[str, Any]) -> list[_Row]:
    """표의 한 행을 한 줄로. 여러 행에 걸친 칸(rowSpan > 1)은 시작 행에만 넣습니다."""
    by_row: dict[int, list[dict[str, Any]]] = {}
    for cell in table.get("cells") or []:
        by_row.setdefault(int(cell.get("rowIndex", 0)), []).append(cell)

    rows: list[_Row] = []
    for _, cells in sorted(by_row.items()):
        words: list[OcrWord] = []
        tops: list[float] = []
        for cell in sorted(cells, key=lambda c: int(c.get("columnIndex", 0))):
            if (b := _box(cell)) is not None:
                tops.append(b.top)
            for text_line in cell.get("cellTextLines") or []:
                for w in text_line.get("cellWords") or []:
                    text = (w.get("inferText") or "").strip()
                    if text:
                        words.append(OcrWord(text, _conf(w)))
        if words:
            rows.append(_Row(top=min(tops) if tops else 0.0, words=words))
    return rows


def _field_rows(fields: list[dict[str, Any]], table_boxes: list[_Box]) -> list[_Row]:
    """표 밖 글자를 줄로 묶습니다. 표 안 글자는 표 행에서 이미 다루므로 건너뜁니다.

    lineBreak가 true면 그 단어에서 줄을 끊습니다. lineBreak가 없거나(V1) 표를 건너뛰어 끊김이 빠진
    경우를 위해, 다음 단어가 지금 줄과 세로로 반 줄 넘게 떨어져 있으면 새 줄로 나눕니다.
    """
    rows: list[_Row] = []
    cur: list[OcrWord] = []
    cur_box: _Box | None = None

    def flush() -> None:
        nonlocal cur, cur_box
        if cur:
            rows.append(_Row(top=cur_box.top if cur_box else 0.0, words=cur))
        cur, cur_box = [], None

    for f in fields:
        text = (f.get("inferText") or "").strip()
        b = _box(f)
        if b is not None and any(t.contains(b.cx, b.cy) for t in table_boxes):
            continue
        if not text:
            if f.get("lineBreak"):
                flush()
            continue
        if cur and b is not None and cur_box is not None and abs(b.cy - cur_box.cy) > max(b.height, cur_box.height) / 2:
            flush()
        cur.append(OcrWord(text, _conf(f)))
        if b is not None:
            cur_box = (
                b
                if cur_box is None
                else _Box(
                    min(cur_box.top, b.top),
                    max(cur_box.bottom, b.bottom),
                    min(cur_box.left, b.left),
                    max(cur_box.right, b.right),
                )
            )
        if f.get("lineBreak"):
            flush()
    flush()
    return rows


def parse_clova_response(data: dict[str, Any]) -> list[OcrLine]:
    """CLOVA General OCR(V2) 응답 한 건(이미지 1장)을 줄 목록으로 바꿉니다.

    인식 실패(inferResult가 SUCCESS가 아님)면 ClovaOcrError. 글자가 하나도 없으면 빈 목록을 돌려주고,
    '글자 없음(no_text)' 판단은 부르는 쪽의 is_no_text()가 합니다.
    """
    images = data.get("images") or []
    if not images:
        raise ClovaOcrError("CLOVA 응답에 images가 없습니다")
    image = images[0]
    result = image.get("inferResult")
    if result != "SUCCESS":
        raise ClovaOcrError(f"CLOVA 인식 실패: inferResult={result}")

    tables = image.get("tables") or []
    table_boxes = [b for t in tables if (b := _box(t)) is not None]
    rows = [row for t in tables for row in _table_rows(t)]
    rows += _field_rows(image.get("fields") or [], table_boxes)
    rows.sort(key=lambda r: r.top)  # 같은 높이면 원래 순서 유지(sort는 안정 정렬)
    return [make_line(0, i, r.words) for i, r in enumerate(rows)]


# ---------------------------------------------------------------------------
# 클라이언트
# ---------------------------------------------------------------------------
def _image_format(image: bytes) -> str:
    if image[:3] == b"\xff\xd8\xff":
        return "jpg"
    if image[:8] == b"\x89PNG\r\n\x1a\n":
        return "png"
    # 페이지 이미지는 업로드 단계에서 jpg·png로 검사·변환되어 옵니다(PDF는 페이지마다 png로 바꿈).
    raise ClovaOcrError("CLOVA에 보낼 수 없는 이미지 형식입니다(jpg·png만)")


class ClovaOcrClient:
    """scan_service.OcrClient 구현. read_page()는 이미지 1장을 읽어 줄 목록을 돌려줍니다.

    http_client를 넘기면 그걸 쓰고(앱 전체에서 하나를 나눠 쓰거나 테스트에서 MockTransport를 물릴 때),
    없으면 직접 만들고 aclose()로 닫습니다.
    """

    def __init__(
        self,
        invoke_url: str,
        secret: str,
        *,
        lang: str = "ko",
        table_detection: bool = True,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        if not invoke_url or not secret:
            raise ValueError("CLOVA_OCR_URL, CLOVA_OCR_SECRET이 필요합니다")
        self._url = invoke_url
        self._secret = secret
        self._lang = lang
        self._table_detection = table_detection
        self._own_client = http_client is None
        self._http = http_client or httpx.AsyncClient(timeout=CLOVA_HTTP_TIMEOUT_SEC)

    @classmethod
    def from_env(cls, **kwargs: Any) -> ClovaOcrClient:
        # ⚠ PR #27(공통 테이블)이 app/core/config.py를 고치는 중이라 충돌을 피해 환경 변수를 직접 읽습니다.
        #    머지 후 Config에 CLOVA_OCR_URL·CLOVA_OCR_SECRET을 옮길 예정.
        return cls(os.environ.get("CLOVA_OCR_URL", ""), os.environ.get("CLOVA_OCR_SECRET", ""), **kwargs)

    def build_request_body(self, image: bytes) -> dict[str, Any]:
        return {
            "version": "V2",
            "requestId": str(uuid.uuid4()),
            "timestamp": int(time.time() * 1000),
            "lang": self._lang,
            "images": [
                {"format": _image_format(image), "name": "page", "data": base64.b64encode(image).decode("ascii")}
            ],
            "enableTableDetection": self._table_detection,
        }

    async def read_page(self, image: bytes) -> list[OcrLine]:
        body = self.build_request_body(image)
        try:
            resp = await self._http.post(self._url, json=body, headers={"X-OCR-SECRET": self._secret})
        except httpx.HTTPError as e:
            raise ClovaOcrError(f"CLOVA 호출 실패: {type(e).__name__}") from None
        if resp.status_code != 200:
            raise ClovaOcrError(f"CLOVA 응답 오류: HTTP {resp.status_code}{_error_code(resp)}")
        try:
            data = resp.json()
        except ValueError:
            raise ClovaOcrError("CLOVA 응답을 JSON으로 읽을 수 없습니다") from None
        return parse_clova_response(data)

    async def aclose(self) -> None:
        if self._own_client:
            await self._http.aclose()


def _error_code(resp: httpx.Response) -> str:
    """오류 응답의 code만 꺼냅니다(메시지 본문은 넣지 않음)."""
    try:
        code = resp.json().get("code")
    except (ValueError, AttributeError):
        return ""
    return f" (code={code})" if code else ""
