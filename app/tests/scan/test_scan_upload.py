"""POST /scans 파일 검사 (명세 6장, 6-3). 테스트 파일은 Pillow로 그때그때 만들고,
암호 PDF만 fixtures/upload/encrypted.pdf(암호 'pw', 2쪽)를 씁니다."""

import io
import zlib
from pathlib import Path

import pypdfium2 as pdfium
import pytest
from PIL import Image

from app.core.exceptions import ErrorCode
from app.services import scan_upload as su
from app.services.scan_upload import UploadedFile, UploadError, detect_kind, prepare_pages, read_uploads

ENCRYPTED_PDF = (Path(__file__).parent / "fixtures" / "upload" / "encrypted.pdf").read_bytes()


def image_bytes(fmt: str = "PNG", size=(120, 80)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, "white").save(buf, fmt)
    return buf.getvalue()


def pdf_bytes(pages: int) -> bytes:
    imgs = [Image.new("RGB", (100, 60), "white") for _ in range(pages)]
    buf = io.BytesIO()
    imgs[0].save(buf, "PDF", save_all=True, append_images=imgs[1:])
    return buf.getvalue()


def f(data: bytes, name: str = "x") -> UploadedFile:
    return UploadedFile(name, data)


def error_of(files) -> UploadError:
    with pytest.raises(UploadError) as e:
        prepare_pages(files)
    return e.value


# ---------------------------------------------------------------------------
# 통과
# ---------------------------------------------------------------------------
def test_photo_and_pdf_pages_numbered_in_upload_order():
    # 사진 1장 + 3쪽 PDF + 사진 1장 → 1, 2, 3, 4, 5 (PDF는 그 자리에 펼침)
    pages = prepare_pages([f(image_bytes("JPEG"), "앞.jpg"), f(pdf_bytes(3), "처방.pdf"), f(image_bytes(), "뒤.png")])
    assert [p.page_no for p in pages] == [1, 2, 3, 4, 5]
    assert [p.file_index for p in pages] == [0, 1, 1, 1, 2]
    assert [p.mime_type for p in pages] == ["image/jpeg"] + ["application/pdf"] * 3 + ["image/png"]
    assert [p.image_kind for p in pages] == ["jpg", "png", "png", "png", "png"]
    assert pages[1].original_name == "처방.pdf" and pages[1].file_size_bytes == pages[3].file_size_bytes


def test_photo_kept_as_is():
    data = image_bytes("JPEG")
    (page,) = prepare_pages([f(data)])
    assert page.image == data


def test_pdf_page_rendered_to_png():
    (page,) = prepare_pages([f(pdf_bytes(1))])
    assert detect_kind(page.image) == "png"
    with Image.open(io.BytesIO(page.image)) as img:
        assert img.size == (round(100 * su.PDF_RENDER_SCALE), round(60 * su.PDF_RENDER_SCALE))


def test_exactly_max_pages_is_ok():
    assert len(prepare_pages([f(pdf_bytes(su.MAX_PAGES))])) == su.MAX_PAGES


# ---------------------------------------------------------------------------
# 실패 (6-3)
# ---------------------------------------------------------------------------
def test_one_file_too_large(monkeypatch):
    small = image_bytes(size=(1, 1))
    monkeypatch.setattr(su, "MAX_FILE_BYTES", len(small) + 10)
    e = error_of([f(small), f(b"\xff\xd8\xff" + b"0" * (len(small) + 50))])
    assert e.code == ErrorCode.FILE_TOO_LARGE and e.status_code == 413 and e.file_index == 1


def test_total_too_large(monkeypatch):
    data = image_bytes()
    monkeypatch.setattr(su, "MAX_TOTAL_BYTES", len(data) * 2)  # 하나씩은 괜찮지만 셋을 합치면 넘음
    e = error_of([f(data), f(data), f(data)])
    assert e.code == ErrorCode.FILE_TOO_LARGE and e.file_index is None


@pytest.mark.parametrize("data", [b"GIF89a....", b"hello", b"", b"PK\x03\x04 zip"])
def test_unsupported_type_by_content(data):
    e = error_of([f(data, "이름만.jpg")])  # 확장자가 jpg여도 내용으로 판단
    assert e.code == ErrorCode.UNSUPPORTED_FILE_TYPE and e.status_code == 415


def test_encrypted_pdf():
    e = error_of([f(image_bytes()), f(ENCRYPTED_PDF)])
    assert e.code == ErrorCode.ENCRYPTED_PDF and e.status_code == 422 and e.file_index == 1


@pytest.mark.parametrize(
    "data",
    [
        b"%PDF-1.4 broken",  # 앞부분만 PDF
        image_bytes()[:40],  # 잘린 PNG
        b"\xff\xd8\xff\xe0" + b"\x00" * 30,  # 앞부분만 JPEG
    ],
)
def test_invalid_file(data):
    e = error_of([f(data)])
    assert e.code == ErrorCode.INVALID_FILE and e.status_code == 422


def test_too_many_pages_counted_before_rendering(monkeypatch):
    rendered = []
    monkeypatch.setattr(su, "_render_pdf", lambda pdf, i: rendered.append(i) or [])
    e = error_of([f(image_bytes()), f(pdf_bytes(su.MAX_PAGES))])  # 1 + 10 = 11장
    assert e.code == ErrorCode.TOO_MANY_PAGES and e.file_index is None
    assert rendered == []  # 넘는 걸 알면 PDF를 그리지 않음


def test_error_message_is_screen_text():
    e = error_of([f(ENCRYPTED_PDF)])
    assert e.message == "암호가 걸린 PDF는 읽을 수 없어요. 암호를 푼 파일이나 사진으로 올려 주세요"


# ---------------------------------------------------------------------------
# 위험한 파일 (#86 리뷰): 작은 파일이 열면 엄청 커지는 경우
# ---------------------------------------------------------------------------
def png_with_header_size(width: int, height: int) -> bytes:
    """1×1 PNG의 머리 부분(IHDR)만 큰 크기로 바꾼 파일. 픽셀은 만들지 않아 테스트가 메모리를 쓰지 않음."""
    data = bytearray(image_bytes(size=(1, 1)))
    ihdr = 8 + 8  # PNG 서명 8바이트 + 길이·종류 8바이트 뒤가 IHDR 내용
    data[ihdr : ihdr + 8] = width.to_bytes(4, "big") + height.to_bytes(4, "big")
    data[ihdr + 13 : ihdr + 17] = zlib.crc32(bytes(data[ihdr - 4 : ihdr + 13])).to_bytes(4, "big")
    return bytes(data)


@pytest.mark.parametrize(
    "width, height",
    [
        (20_000, 20_000),  # 4억 픽셀: Pillow가 열기부터 거절(DecompressionBombError)
        (10_000, 10_000),  # 1억 픽셀: Pillow는 경고만 하고 통과시키는 구간
        (7_000, 7_000),  # 4900만 픽셀: 우리 상한(MAX_IMAGE_PIXELS) 초과
    ],
)
def test_decompression_bomb_image_is_invalid(width, height):
    e = error_of([f(png_with_header_size(width, height))])
    assert e.code == ErrorCode.INVALID_FILE and e.file_index == 0


def test_large_but_normal_photo_passes():
    # 휴대폰 사진 정도(4000×3000 = 1200만 픽셀)는 통과
    (page,) = prepare_pages([f(png_with_header_size(4000, 3000))])
    assert page.page_no == 1


def huge_page_pdf(side_pt: float) -> bytes:
    pdf = pdfium.PdfDocument.new()
    pdf.new_page(side_pt, side_pt)
    buf = io.BytesIO()
    pdf.save(buf)
    pdf.close()
    return buf.getvalue()


def test_huge_pdf_page_rendered_within_max_side(monkeypatch):
    monkeypatch.setattr(su, "MAX_RENDER_SIDE", 500)  # 테스트를 가볍게. 실제 값은 4000
    data = huge_page_pdf(200 * 72)  # 200인치 × 200인치, 파일은 수백 바이트
    (page,) = prepare_pages([f(data)])
    with Image.open(io.BytesIO(page.image)) as img:
        assert max(img.size) <= 500


def test_normal_pdf_page_keeps_render_scale():
    # A4(595×842pt)는 2배율이면 긴 변 1684로 상한(4000)보다 작아 배율을 줄이지 않음
    (page,) = prepare_pages([f(huge_page_pdf(842))])
    with Image.open(io.BytesIO(page.image)) as img:
        assert max(img.size) == round(842 * su.PDF_RENDER_SCALE)


def empty_pdf() -> bytes:
    empty = pdfium.PdfDocument.new()
    buf = io.BytesIO()
    empty.save(buf)
    empty.close()
    return buf.getvalue()


def test_empty_pdf_reports_its_file_index():
    e = error_of([f(image_bytes()), f(empty_pdf())])  # 사진 + 쪽이 없는 PDF
    assert e.code == ErrorCode.INVALID_FILE and e.file_index == 1


def test_broken_pdf_after_encrypted_pdf_is_not_called_encrypted():
    # PDFium이 이전 호출의 '비밀번호 오류' 코드를 그대로 돌려주는 경우가 있어, 순서와 상관없이 맞게 나와야 함
    assert error_of([f(ENCRYPTED_PDF)]).code == ErrorCode.ENCRYPTED_PDF
    assert error_of([f(empty_pdf())]).code == ErrorCode.INVALID_FILE
    assert error_of([f(b"%PDF-1.4 broken")]).code == ErrorCode.INVALID_FILE


# ---------------------------------------------------------------------------
# read_uploads: 한도까지만 읽기
# ---------------------------------------------------------------------------
class FakeUpload:
    def __init__(self, name: str, data: bytes):
        self.filename = name
        self._buf = io.BytesIO(data)
        self.asked: list[int] = []

    async def read(self, size: int = -1) -> bytes:
        self.asked.append(size)
        return self._buf.read(size)


async def test_read_uploads_reads_at_most_limit_plus_one(monkeypatch):
    monkeypatch.setattr(su, "MAX_FILE_BYTES", 10)
    big = FakeUpload("big.jpg", b"x" * 1000)
    with pytest.raises(su.UploadError) as e:
        await read_uploads([big])
    assert e.value.code == ErrorCode.FILE_TOO_LARGE and e.value.file_index == 0
    assert big.asked == [11]  # 전체를 읽지 않고 한도 + 1바이트만


async def test_read_uploads_stops_when_total_exceeded(monkeypatch):
    monkeypatch.setattr(su, "MAX_TOTAL_BYTES", 15)
    first, second, third = FakeUpload("a", b"x" * 10), FakeUpload("b", b"x" * 10), FakeUpload("c", b"x")
    with pytest.raises(su.UploadError) as e:
        await read_uploads([first, second, third])
    assert e.value.code == ErrorCode.FILE_TOO_LARGE and e.value.file_index is None
    assert third.asked == []  # 합계를 넘으면 남은 파일은 읽지 않음


async def test_read_uploads_keeps_names_and_order():
    files = await read_uploads([FakeUpload("앞.jpg", b"1"), FakeUpload("뒤.jpg", b"2")])
    assert [(f.name, f.data) for f in files] == [("앞.jpg", b"1"), ("뒤.jpg", b"2")]
