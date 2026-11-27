"""POST /scans 파일 검사 (명세 6장, 6-3). 테스트 파일은 Pillow로 그때그때 만들고,
암호 PDF만 fixtures/upload/encrypted.pdf(암호 'pw', 2쪽)를 씁니다."""

import io
from pathlib import Path

import pytest
from PIL import Image

from app.dtos.scan import ScanErrorCode
from app.services import scan_upload as su
from app.services.scan_upload import UploadedFile, UploadError, detect_kind, prepare_pages

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
    assert e.code == ScanErrorCode.FILE_TOO_LARGE and e.status_code == 413 and e.file_index == 1


def test_total_too_large(monkeypatch):
    data = image_bytes()
    monkeypatch.setattr(su, "MAX_TOTAL_BYTES", len(data) * 2)  # 하나씩은 괜찮지만 셋을 합치면 넘음
    e = error_of([f(data), f(data), f(data)])
    assert e.code == ScanErrorCode.FILE_TOO_LARGE and e.file_index is None


@pytest.mark.parametrize("data", [b"GIF89a....", b"hello", b"", b"PK\x03\x04 zip"])
def test_unsupported_type_by_content(data):
    e = error_of([f(data, "이름만.jpg")])  # 확장자가 jpg여도 내용으로 판단
    assert e.code == ScanErrorCode.UNSUPPORTED_FILE_TYPE and e.status_code == 415


def test_encrypted_pdf():
    e = error_of([f(image_bytes()), f(ENCRYPTED_PDF)])
    assert e.code == ScanErrorCode.ENCRYPTED_PDF and e.status_code == 422 and e.file_index == 1


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
    assert e.code == ScanErrorCode.INVALID_FILE and e.status_code == 422


def test_too_many_pages_counted_before_rendering(monkeypatch):
    rendered = []
    monkeypatch.setattr(su, "_render_pdf", lambda pdf, i: rendered.append(i) or [])
    e = error_of([f(image_bytes()), f(pdf_bytes(su.MAX_PAGES))])  # 1 + 10 = 11장
    assert e.code == ScanErrorCode.TOO_MANY_PAGES and e.file_index is None
    assert rendered == []  # 넘는 걸 알면 PDF를 그리지 않음


def test_error_message_is_screen_text():
    e = error_of([f(ENCRYPTED_PDF)])
    assert e.message == "암호가 걸린 PDF는 읽을 수 없어요. 암호를 푼 파일이나 사진으로 올려 주세요"
