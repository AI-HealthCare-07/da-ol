"""빠진 약 찾기 (이슈 #45). 실제 CLOVA 응답(fixtures/clova/real, 가상 데이터)으로 확인합니다."""

import asyncio

import pytest

import app.services.scan_service as sp
from app.dtos.scan import DrugMatch, MatchStatus
from app.services.missing_drugs import find_possibly_missing_drugs, find_unlinked_drug_lines
from app.tests.test_clova_real import EXPECTED_DRUGS, lines_of, nospace

W = sp.OcrWord


def masked_lines(case: int) -> list[sp.OcrLine]:
    return sp.mask_lines(lines_of(case))  # 실제 파이프라인처럼 가린 뒤의 줄


def drug_line_refs(lines: list[sp.OcrLine], drugs: list[str]) -> dict[str, str]:
    """정답 약 이름 → 그 약이 있는 줄(ref). LLM이 제대로 연결했다고 가정할 때 쓰는 값."""
    refs = {}
    for drug in drugs:
        refs[drug] = next(ln.ref for ln in lines if drug in nospace(ln.text))
    return refs


# ---------------------------------------------------------------------------
# 오탐 없음: LLM이 약을 다 연결하면 아무것도 안 잡혀야 함 (머리글·안내문·잘못 읽힌 글 포함)
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("case, drugs", EXPECTED_DRUGS.items())
def test_no_candidates_when_all_drugs_linked(case, drugs):
    lines = masked_lines(case)
    linked = set(drug_line_refs(lines, drugs).values())
    assert find_unlinked_drug_lines(lines, linked) == []


# ---------------------------------------------------------------------------
# 누락 탐지: 약 하나를 연결에서 빼면 그 줄이 잡혀야 함
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "case, dropped",
    [(case, drug) for case, drugs in EXPECTED_DRUGS.items() for drug in drugs],
)
def test_dropped_drug_is_found(case, dropped):
    lines = masked_lines(case)
    refs = drug_line_refs(lines, EXPECTED_DRUGS[case])
    linked = {ref for drug, ref in refs.items() if drug != dropped}
    found = find_unlinked_drug_lines(lines, linked)
    assert [c.line_idx for c in found] == [int(refs[dropped].split("-l")[1])]
    assert nospace(found[0].drug_name).startswith(dropped)


def test_case10_dropped_gasmotin_keeps_strength_and_text():
    # case10 원래 목적: 마지막 약(가스모틴정)이 통째로 빠지는 경우
    lines = masked_lines(10)
    refs = drug_line_refs(lines, EXPECTED_DRUGS[10])
    linked = {refs["트라젠타정"], refs["아토르바스타틴정"]}
    (cand,) = find_unlinked_drug_lines(lines, linked)
    assert cand.drug_name == "가스모틴정 5mg"
    assert cand.raw_text == "가스모틴정 5mg 1정 3회 30일 식후 30분"
    assert cand.page_no == 0 and cand.line_idx == 6


# ---------------------------------------------------------------------------
# 규칙 단위
# ---------------------------------------------------------------------------
def line(*words: str) -> sp.OcrLine:
    return sp.make_line(1, 0, [W(w, 0.99) for w in words])


@pytest.mark.parametrize(
    "words, name",
    [
        (("가스모틴정", "5mg", "1정", "3회", "30일"), "가스모틴정 5mg"),
        (("가상정5mg", "1정", "3회"), "가상정5mg"),
        (("히알유니점안액0.15%", "1방울", "4회", "14일"), "히알유니점안액0.15%"),
        (("에스로반연고", "적당량", "2회", "7일"), "에스로반연고"),
        (("코대원포르테시럽", "20mL", "3회", "3일"), "코대원포르테시럽"),
        (("알마겔정(알마게이트)", "1정", "3회"), "알마겔정(알마게이트)"),
    ],
)
def test_drug_like_line(words, name):
    (cand,) = find_unlinked_drug_lines([line(*words)], set())
    assert cand.drug_name == name


@pytest.mark.parametrize(
    "words",
    [
        ("의약품명", "1회", "투약량", "1일", "투여횟수", "총", "투약일수"),  # 머리글
        ("복약안내", "식사", "후", "30분", "복용"),  # 안내문
        ("1정", "1회", "30일", "100mg", "분"),  # 이름 없는 조각 줄 (case07 실제 응답)
        ("다음", "진료", "예정", "3일"),  # '정'으로 끝나는 일반 단어(한글 2자 + 정은 약 이름으로 안 봄)
        ("가스모틴정", "5mg"),  # 약 이름만 있고 용량·횟수·일수가 없음
        ("주민등록번호:", "[주민번호]", "3일"),
    ],
)
def test_not_drug_like_line(words):
    assert find_unlinked_drug_lines([line(*words)], set()) == []


# ---------------------------------------------------------------------------
# 2단계: 약 DB에 비슷한 약이 있을 때만
# ---------------------------------------------------------------------------
class OnlyKnownCatalog:
    async def match(self, name):
        if nospace(name).startswith("가스모틴정"):
            return DrugMatch(status=MatchStatus.EXACT, drug_id=1022, candidates=[]), True
        return DrugMatch(status=MatchStatus.NONE, drug_id=None, candidates=[]), None

    async def get_many(self, drug_ids):
        return {}


def test_catalog_filters_unknown_names():
    lines = [line("가스모틴정", "5mg", "1정", "3회", "30일"), line("다올비타정", "1정", "1회")]
    lines = [sp.make_line(1, i, ln.words) for i, ln in enumerate(lines)]
    assert len(find_unlinked_drug_lines(lines, set())) == 2  # 1단계에서는 둘 다 후보(약 DB에 없는 이름 포함)
    found = asyncio.run(find_possibly_missing_drugs(lines, set(), OnlyKnownCatalog()))
    assert [c.drug_name for c in found] == ["가스모틴정 5mg"]
