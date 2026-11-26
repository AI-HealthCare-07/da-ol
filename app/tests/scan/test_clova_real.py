"""실제 CLOVA 응답(fixtures/clova/real, 테스트 처방 이미지 = 가상 데이터)으로 확인하는 테스트.

파싱 규칙의 세부 동작은 test_clova_ocr.py의 예시 fixture로 확인하고,
여기서는 진짜 응답 형식에서도 결과가 맞는지 확인합니다.
"""

import json
from pathlib import Path

import pytest

import app.services.scan_service as sp
from app.services.clova_ocr import parse_clova_response

REAL = Path(__file__).parent / "fixtures" / "clova" / "real"

EXPECTED_DRUGS = {
    4: ["코대원포르테시럽", "펠루비정", "무코스타정"],
    7: ["노바스크정", "다이아벡스정", "크레스토정", "아스피린프로텍트정"],
    10: ["트라젠타정", "아토르바스타틴정", "가스모틴정"],
    11: ["세토펜정", "베아제정"],
    12: ["아모잘탄정", "무코스타정"],
}


def lines_of(case: int) -> list[sp.OcrLine]:
    data = json.loads((REAL / f"case{case:02d}.json").read_text(encoding="utf-8"))
    return parse_clova_response(data)


def nospace(s: str) -> str:
    return "".join(s.split())


@pytest.mark.parametrize("case", EXPECTED_DRUGS)
def test_real_line_numbers_and_word_positions(case):
    lines = lines_of(case)
    assert [ln.line_idx for ln in lines] == list(range(len(lines)))
    for ln in lines:
        assert all(ln.text[w.start : w.end] == w.text for w in ln.words)


@pytest.mark.parametrize("case, drugs", EXPECTED_DRUGS.items())
def test_real_drug_names_found(case, drugs):
    joined = nospace(" ".join(ln.text for ln in lines_of(case)))
    for drug in drugs:
        assert drug in joined, drug


def test_real_case11_name_before_gwiha_masked():
    texts = [ln.text for ln in sp.mask_lines(lines_of(11))]
    assert not any("김다올" in t for t in texts)
    assert any(t.startswith("[이름]") and "귀하" in t for t in texts)


def test_real_case12_split_phone_masked():
    texts = [ln.text for ln in sp.mask_lines(lines_of(12))]
    joined = nospace(" ".join(texts))
    for value in ["김다올", "000101-3000000", "010-0000-0000", "0000-0000"]:
        assert value not in joined, value
    assert any(t.endswith("연락처: [연락처]") for t in texts)
