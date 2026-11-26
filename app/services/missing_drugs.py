"""빠진 약 찾기 (AI 검증 규칙: 빠진 약, 이슈 #45) — 담당: AI A 채민

LLM이 정리하면서 약 줄을 통째로 빠뜨리면 drugs에 그 줄이 없어서 칸 신뢰도(needs_check)로는 잡을 수 없습니다.
그래서 OCR 줄과 LLM 결과를 맞대 봅니다.

1. 후보 고르기(정규식, find_unlinked_drug_lines): LLM 결과의 어떤 약(line_ref)과도 연결되지 않은 줄 중에서
   - 한글 2자 이상 + 제형(정·캡슐·시럽·액·연고 등)으로 끝나는 단어가 있고
   - 같은 줄에 용량·횟수·일수 숫자(1정, 3회, 30일 등)도 있는 줄
   → 머리글(의약품명 1회 투약량 …)·안내문(식사 후 30분 복용)·'예정' 같은 일반 단어는 여기서 걸러집니다.
2. 약 DB 확인(find_possibly_missing_drugs): 후보 줄의 약 이름을 DrugCatalog.match()로 찾아
   비슷한 약이 있을 때만 '빠진 약일 수 있음'으로 봅니다.

잡는 것: OCR은 읽었는데 LLM이 빠뜨린 약.
못 잡는 것: OCR이 아예 못 읽은 줄(대조할 줄이 없음).

응답 형식(possibly_missing)과 화면 연결은 다음 단계입니다(설아님과 화면 문구 정한 뒤).
줄은 가린 뒤의 글자(mask_lines 결과)를 넘깁니다.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.dtos.scan import MatchStatus
from app.services.scan_service import DrugCatalog, OcrLine

# 약 이름 끝에 오는 제형. 긴 표현부터 검사해야 '점안액'이 '액'으로 먼저 끝나지 않습니다.
_DRUG_FORMS = sorted(
    [
        "정", "정제", "캡슐", "캅셀", "시럽", "현탁액", "액", "산", "과립", "세립", "환",
        "연고", "크림", "겔", "로션", "패취", "패치", "점안액", "점안제", "주", "주사액", "좌제",
    ],
    key=len,
    reverse=True,
)  # fmt: skip
_FORM_RE = "|".join(_DRUG_FORMS)
# 약 이름 단어: 한글 2자 이상을 포함하고 제형으로 끝남. 뒤에 함량(5mg)·괄호가 붙어도 됨
_DRUG_WORD_RE = re.compile(
    rf"^(?P<name>\S*?[가-힣]{{2,}}\S*?(?:{_FORM_RE}))"
    r"(?P<strength>[\d.,/]+(?:mg|g|mL|ml|mcg|%|밀리그램|그램|밀리그람)?)?"
    r"(?:\(.*)?$"
)
# 같은 줄의 용량·횟수·일수 단어
_COUNT_WORD_RE = re.compile(r"^(?:\d+(?:[./]\d+)?(?:정|캡슐|포|mL|ml|cc|g|방울|회|일|T|C)|적당량)$", re.IGNORECASE)
# 이름 바로 뒤에 떨어져 오는 함량 단어(5mg, 5/50mg, 0.15%). mL·g는 1회 용량(시럽 20mL 등)과 헷갈려 뺌
_STRENGTH_WORD_RE = re.compile(r"^[\d.,/]+(?:mg|mcg|%|밀리그램|밀리그람)$", re.IGNORECASE)


@dataclass(frozen=True)
class MissingDrugCandidate:
    page_no: int
    line_idx: int
    raw_text: str  # 가린 줄 글자 그대로 (화면에 "○○이 목록에 없어요"로 보여 줄 때)
    drug_name: str  # 약 이름 단어 + 바로 뒤 함량 (약 추가 때 미리 채울 값)


def _drug_name_in(line: OcrLine) -> str | None:
    """줄에서 약 이름을 찾습니다. 같은 줄에 용량·횟수·일수 단어가 없으면 약 줄로 보지 않습니다."""
    words = [w.text for w in line.words]
    for i, word in enumerate(words):
        m = _DRUG_WORD_RE.match(word)
        if not m:
            continue
        others = words[:i] + words[i + 1 :]
        if not any(_COUNT_WORD_RE.match(w) for w in others):
            continue
        name = word
        if not m.group("strength") and i + 1 < len(words) and _STRENGTH_WORD_RE.match(words[i + 1]):
            name = f"{word} {words[i + 1]}"
        return name
    return None


def find_unlinked_drug_lines(lines: list[OcrLine], linked_refs: set[str]) -> list[MissingDrugCandidate]:
    """1단계(순수 함수): LLM 결과와 연결되지 않은 줄 중 약 줄처럼 보이는 줄.

    linked_refs: LLM 결과 drugs[].line_ref 모음(예: {"p1-l4", "p1-l5"}).
    """
    found = []
    for line in lines:
        if line.ref in linked_refs:
            continue
        name = _drug_name_in(line)
        if name:
            found.append(MissingDrugCandidate(line.page_no, line.line_idx, line.text, name))
    return found


async def find_possibly_missing_drugs(
    lines: list[OcrLine], linked_refs: set[str], catalog: DrugCatalog
) -> list[MissingDrugCandidate]:
    """2단계: 1단계 후보 중 약 DB에 비슷한 약이 있는 줄만 남깁니다(오탐 줄이기)."""
    result = []
    for cand in find_unlinked_drug_lines(lines, linked_refs):
        match, _ = await catalog.match(cand.drug_name)
        if match.status != MatchStatus.NONE:
            result.append(cand)
    return result
