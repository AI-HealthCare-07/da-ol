"""POST /scans 파일 검사 (명세 6장 POST /scans, 6-3 에러 코드) — 담당: AI A 채민

요청을 받을 때 크기·형식·암호·손상·페이지 수를 모두 검사하고, 통과하면 페이지 이미지 목록을 돌려줍니다.
통과한 경우에만 202를 돌려주므로(명세 비고) 이 단계에서 실패하면 문서 행을 만들지 않습니다.

- 형식은 확장자가 아니라 파일 내용(앞 몇 바이트)으로 판단합니다.
- PDF는 페이지마다 PNG 이미지로 바꾸고, 그 파일 자리에 펼쳐서 번호를 매깁니다
  (사진 1장 + 3쪽 PDF → 1, 2, 3, 4).
- 검사 순서: 크기(싸게 먼저) → 형식 → 열기(암호·손상) → 전체 페이지 수 → PDF 그리기.
  페이지 수는 그리기 전에 세서, 10장을 넘는 PDF를 쓸데없이 그리지 않습니다.

DB·외부 호출이 없는 순수 함수입니다. 라우터는 UploadError를 1-1 에러 형식으로 바꿔 돌려줍니다.
"""

from __future__ import annotations

import io
import warnings
from dataclasses import dataclass
from typing import Protocol

import pypdfium2 as pdfium
from PIL import Image, UnidentifiedImageError

from app.dtos.scan import ScanErrorCode
from app.services.scan_service import MAX_FILE_BYTES, MAX_PAGES, MAX_TOTAL_BYTES

# PDF 그리기 배율. 1 = 72dpi. 2 ≈ 144dpi로 처방전 글자를 읽기에 충분하고 메모리도 적게 씀(12/9 메모리 측정 때 조정)
PDF_RENDER_SCALE = 2.0
# 그린 PDF 페이지의 긴 변 상한(픽셀). 페이지 크기가 비정상적으로 큰 PDF가 메모리를 다 쓰지 않게 배율을 줄임.
# A4는 2배율이면 1190×1684라 보통 처방전에는 영향 없음
MAX_RENDER_SIDE = 4000
# 사진 픽셀 수 상한. 작은 파일이 열면 엄청 커지는 사진(압축 폭탄)을 막음. 휴대폰 사진(약 1200만~5000만)보다 넉넉하게
MAX_IMAGE_PIXELS = 40_000_000
_PDFIUM_PASSWORD_ERROR = 4  # FPDF_ERR_PASSWORD

MIME_BY_KIND = {"jpg": "image/jpeg", "png": "image/png", "pdf": "application/pdf"}

# 6-3 화면 문구
MESSAGES = {
    ScanErrorCode.FILE_TOO_LARGE: "파일 용량이 너무 커요. 한 개에 10MB, 모두 합쳐 30MB까지 올릴 수 있어요",
    ScanErrorCode.UNSUPPORTED_FILE_TYPE: "jpg, png, pdf 파일만 올릴 수 있어요",
    ScanErrorCode.ENCRYPTED_PDF: "암호가 걸린 PDF는 읽을 수 없어요. 암호를 푼 파일이나 사진으로 올려 주세요",
    ScanErrorCode.INVALID_FILE: "파일을 열 수 없어요. 다른 파일로 다시 올려 주세요",
    ScanErrorCode.TOO_MANY_PAGES: f"한 번에 {MAX_PAGES}장까지 올릴 수 있어요",
}
STATUS_CODES = {
    ScanErrorCode.FILE_TOO_LARGE: 413,
    ScanErrorCode.UNSUPPORTED_FILE_TYPE: 415,
    ScanErrorCode.ENCRYPTED_PDF: 422,
    ScanErrorCode.INVALID_FILE: 422,
    ScanErrorCode.TOO_MANY_PAGES: 422,
}


class UploadError(Exception):
    """파일 검사 실패. 라우터가 {code, message}(1-1)로 바꿔 돌려줍니다. 메시지에 파일 내용은 넣지 않습니다."""

    def __init__(self, code: ScanErrorCode, file_index: int | None = None) -> None:
        super().__init__(code.value)
        self.code = code
        self.status_code = STATUS_CODES[code]
        self.message = MESSAGES[code]
        self.file_index = file_index  # 몇 번째 파일 때문인지(0부터). 합계 초과·페이지 초과는 None


@dataclass(frozen=True)
class UploadedFile:
    name: str | None
    data: bytes


@dataclass(frozen=True)
class PageImage:
    """document_pages 한 행이 될 페이지. image는 OCR에 보낼 jpg·png 바이트."""

    page_no: int  # 1부터, 올린 순서대로(PDF는 그 자리에 펼침)
    file_index: int  # 몇 번째 파일에서 나왔는지(0부터)
    original_name: str | None
    mime_type: str  # 원본 파일 형식(document_pages.mime_type)
    file_size_bytes: int  # 원본 파일 크기. PDF는 페이지마다 같은 값(ERD)
    image: bytes
    image_kind: str  # "jpg" / "png" (CLOVA 요청 format)


class ReadableUpload(Protocol):
    """FastAPI UploadFile과 같은 모양(이름 + async read)."""

    filename: str | None

    async def read(self, size: int = -1) -> bytes: ...


async def read_uploads(uploads: list[ReadableUpload]) -> list[UploadedFile]:
    """업로드 파일을 한 개당 MAX_FILE_BYTES + 1바이트까지만 읽습니다.

    다 읽은 뒤에 크기를 재면 아주 큰 파일이 메모리에 통째로 올라오므로, 한도를 넘는 순간 FILE_TOO_LARGE로 막습니다.
    합계(30MB)는 읽으면서 더해 보고, 넘으면 남은 파일은 읽지 않습니다.
    """
    files: list[UploadedFile] = []
    total = 0
    for i, upload in enumerate(uploads):
        data = await upload.read(MAX_FILE_BYTES + 1)
        if len(data) > MAX_FILE_BYTES:
            raise UploadError(ScanErrorCode.FILE_TOO_LARGE, i)
        total += len(data)
        if total > MAX_TOTAL_BYTES:
            raise UploadError(ScanErrorCode.FILE_TOO_LARGE)
        files.append(UploadedFile(upload.filename, data))
    return files


def detect_kind(data: bytes) -> str | None:
    """파일 앞부분으로 형식을 판단합니다. jpg·png·pdf가 아니면 None."""
    if data.startswith(b"\xff\xd8\xff"):
        return "jpg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if data.lstrip()[:5] == b"%PDF-":
        return "pdf"
    return None


def _check_sizes(files: list[UploadedFile]) -> None:
    for i, f in enumerate(files):
        if len(f.data) > MAX_FILE_BYTES:
            raise UploadError(ScanErrorCode.FILE_TOO_LARGE, i)
    if sum(len(f.data) for f in files) > MAX_TOTAL_BYTES:
        raise UploadError(ScanErrorCode.FILE_TOO_LARGE)


def _check_image(data: bytes, index: int) -> None:
    try:
        with warnings.catch_warnings():
            # Pillow는 약 8900만~1억 7900만 픽셀은 경고만 하고 통과시킴. 아래에서 더 낮은 상한으로 직접 막으므로 경고는 끔
            warnings.simplefilter("ignore", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(data)) as img:  # 크기는 머리 부분만 읽어서 알 수 있음
                width, height = img.size
                if width * height > MAX_IMAGE_PIXELS:
                    raise UploadError(ScanErrorCode.INVALID_FILE, index)
                img.verify()  # 잘린 파일·깨진 헤더를 찾음(픽셀은 디코딩하지 않음)
    except Image.DecompressionBombError as e:  # 약 1억 7900만 픽셀 초과: Pillow가 열기부터 거절
        raise UploadError(ScanErrorCode.INVALID_FILE, index) from e
    except (UnidentifiedImageError, OSError, SyntaxError, ValueError) as e:
        raise UploadError(ScanErrorCode.INVALID_FILE, index) from e


def _open_pdf(data: bytes, index: int) -> pdfium.PdfDocument:
    try:
        pdf = pdfium.PdfDocument(data)
    except pdfium.PdfiumError as e:
        # PDFium은 오류 코드를 따로 남기지 않은 실패에서 이전 호출의 코드를 그대로 돌려줄 때가 있음.
        # 그래서 '비밀번호 오류' 코드이면서 파일에 암호 사전(/Encrypt)이 있을 때만 암호 PDF로 봄
        is_encrypted = getattr(e, "err_code", None) == _PDFIUM_PASSWORD_ERROR and b"/Encrypt" in data
        code = ScanErrorCode.ENCRYPTED_PDF if is_encrypted else ScanErrorCode.INVALID_FILE
        raise UploadError(code, index) from e
    if len(pdf) == 0:  # 쪽이 없는 PDF는 그 파일 번호로 알려 줌(다른 파일과 섞여도 몇 번째인지 맞게)
        pdf.close()
        raise UploadError(ScanErrorCode.INVALID_FILE, index)
    return pdf


def _render_scale(page: pdfium.PdfPage) -> float:
    """긴 변이 MAX_RENDER_SIDE를 넘지 않는 배율. 페이지 크기는 포인트(1/72인치) 단위."""
    width, height = page.get_size()
    longest = max(width, height)
    if longest <= 0:
        return PDF_RENDER_SCALE
    return min(PDF_RENDER_SCALE, MAX_RENDER_SIDE / longest)


def _render_pdf(pdf: pdfium.PdfDocument, index: int) -> list[bytes]:
    pages = []
    try:
        for page in pdf:
            buf = io.BytesIO()
            page.render(scale=_render_scale(page)).to_pil().save(buf, "PNG")
            pages.append(buf.getvalue())
    except (pdfium.PdfiumError, OSError, ValueError) as e:
        raise UploadError(ScanErrorCode.INVALID_FILE, index) from e
    return pages


def _detect_kinds(files: list[UploadedFile]) -> list[str]:
    kinds = []
    for i, f in enumerate(files):
        kind = detect_kind(f.data)
        if kind is None:
            raise UploadError(ScanErrorCode.UNSUPPORTED_FILE_TYPE, i)
        kinds.append(kind)
    return kinds


def _open_all(files: list[UploadedFile], kinds: list[str], opened: list[pdfium.PdfDocument | None]) -> None:
    """이미지는 검사만, PDF는 열어서 opened에 담습니다(닫는 건 부른 쪽)."""
    for i, (f, kind) in enumerate(zip(files, kinds, strict=True)):
        if kind == "pdf":
            opened.append(_open_pdf(f.data, i))
        else:
            _check_image(f.data, i)
            opened.append(None)


def _check_page_count(opened: list[pdfium.PdfDocument | None]) -> None:
    total = sum(len(pdf) if pdf is not None else 1 for pdf in opened)
    if total > MAX_PAGES:
        raise UploadError(ScanErrorCode.TOO_MANY_PAGES)


def prepare_pages(files: list[UploadedFile]) -> list[PageImage]:
    """파일을 검사하고 페이지 이미지 목록을 돌려줍니다. 하나라도 실패하면 UploadError.

    파일 없음은 라우터의 요청 검사(VALIDATION_ERROR)에서 막습니다.
    """
    _check_sizes(files)
    kinds = _detect_kinds(files)
    opened: list[pdfium.PdfDocument | None] = []
    try:
        _open_all(files, kinds, opened)
        _check_page_count(opened)
        result: list[PageImage] = []
        for i, (f, kind, pdf) in enumerate(zip(files, kinds, opened, strict=True)):
            images = [(f.data, kind)] if pdf is None else [(img, "png") for img in _render_pdf(pdf, i)]
            for image, image_kind in images:
                result.append(
                    PageImage(
                        page_no=len(result) + 1,
                        file_index=i,
                        original_name=f.name,
                        mime_type=MIME_BY_KIND[kind],
                        file_size_bytes=len(f.data),
                        image=image,
                        image_kind=image_kind,
                    )
                )
        return result
    finally:
        for pdf in opened:
            if pdf is not None:
                pdf.close()
