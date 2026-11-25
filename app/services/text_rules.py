"""
AI A 공용 함수 (API 명세서 6-4)

- parse_dose_text(text): 1회 용량 글자 → {text, min, max, unit, parsed}
- mask_text(text): 개인정보를 [주민번호]·[연락처]·[이메일]·[환자번호]·[면허번호]·[이름]으로 가림
- normalize_drug_name(name): 약품명 매칭용 정규화 (OCR 매칭·GET /drugs·drugs 적재 공용)

두 함수 모두 DB·외부 호출이 없는 순수 함수입니다. 같은 입력이면 항상 같은 결과입니다.
"""
from __future__ import annotations

import re
import unicodedata
from fractions import Fraction
from typing import TypedDict

DOSAGE_DICT_VERSION = "dosage_dict_v1"


# ---------------------------------------------------------------------------
# parse_dose_text
# ---------------------------------------------------------------------------
class DosePerTime(TypedDict):
    text: str
    min: float | None
    max: float | None
    unit: str | None
    parsed: bool


# 표현 사전 v1: 적힌 단위 → 저장·표시할 단위. 테스트하면서 늘립니다.
UNIT_ALIASES: dict[str, str] = {
    "정": "정", "알": "정", "t": "정", "tab": "정", "tablet": "정",
    "캡슐": "캡슐", "c": "캡슐", "cap": "캡슐", "capsule": "캡슐",
    "포": "포", "pk": "포",
    "ml": "mL", "cc": "mL",
    "g": "g",
    "방울": "방울", "gtt": "방울",
}

# 숫자 대신 쓰는 한글 표현
WORD_NUMBERS: dict[str, Fraction] = {"반": Fraction(1, 2), "한": Fraction(1), "두": Fraction(2)}

_NUM = r"(?:\d+\s*/\s*\d+|\d+(?:\.\d+)?|반|한|두)"
_UNIT = "|".join(sorted((re.escape(u) for u in UNIT_ALIASES), key=len, reverse=True))
_DOSE_RE = re.compile(
    rf"^(?P<a>{_NUM})\s*(?:(?:~|-|∼|〜)\s*(?P<b>{_NUM}))?\s*(?P<unit>{_UNIT})\s*(?:씩)?$",
    re.IGNORECASE,
)


def _to_number(token: str) -> Fraction:
    token = token.replace(" ", "")
    if token in WORD_NUMBERS:
        return WORD_NUMBERS[token]
    if "/" in token:
        num, den = token.split("/")
        return Fraction(int(num), int(den))
    return Fraction(token)


def _unparsed(text: str) -> DosePerTime:
    return {"text": text, "min": None, "max": None, "unit": None, "parsed": False}


def parse_dose_text(text: str) -> DosePerTime:
    """1회 용량 글자를 숫자·단위로 읽습니다.

    >>> parse_dose_text("1/2정")
    {'text': '1/2정', 'min': 0.5, 'max': 0.5, 'unit': '정', 'parsed': True}
    >>> parse_dose_text("적당량")["parsed"]
    False
    """
    original = text
    if not text or not text.strip():
        return _unparsed(original)

    normalized = unicodedata.normalize("NFKC", text).strip()
    m = _DOSE_RE.match(normalized)
    if not m:
        return _unparsed(original)

    try:
        low = _to_number(m.group("a"))
        high = _to_number(m.group("b")) if m.group("b") else low
    except (ValueError, ZeroDivisionError):
        return _unparsed(original)

    if low <= 0 or high < low:
        return _unparsed(original)

    unit = UNIT_ALIASES[m.group("unit").lower()]
    return {
        "text": original,
        "min": float(low),
        "max": float(high),
        "unit": unit,
        "parsed": True,
    }


# ---------------------------------------------------------------------------
# mask_text
# ---------------------------------------------------------------------------
# 1) 이름표가 붙은 값: 이름표는 남기고 값만 가립니다. 위치로 알 수 있을 때만 이름을 가립니다(6-4).
_LABELED_RULES: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"((?:환자\s*)?성\s*명|환자명)(\s*[:：]?\s*)([가-힣]{2,5})"), "[이름]"),
    (re.compile(r"((?<!주민)(?:환자|등록|진료|차트)\s*번호)(\s*[:：]?\s*)([A-Za-z0-9\-]+)"), "[환자번호]"),
    (re.compile(r"(면허\s*번호)(\s*[:：]?\s*)([A-Za-z0-9\-]+)"), "[면허번호]"),
]

# 2) 모양만으로 알 수 있는 값
_SHAPE_RULES: list[tuple[re.Pattern[str], str]] = [
    # 주민등록번호: 하이픈 또는 띄어쓰기로 나눈 경우(900101-1234567, 900101 1234567).
    # 뒷자리 일부가 *로 가려진 경우도 포함
    (re.compile(r"(?<!\d)\d{6}(?:\s*-\s*|\s+)[1-8][\d*]{6}(?!\d)"), "[주민번호]"),
    (re.compile(r"(?<!\d)\d{6}[1-8]\d{6}(?!\d)"), "[주민번호]"),
    (re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}"), "[이메일]"),
    # 전화번호: 010-1234-5678, 02)123-4567, 031.123.4567, 010 1234 5678(챗봇에서 띄어 쓴 경우)
    (re.compile(r"(?<!\d)0\d{1,2}\s*[-.)]?\s*\d{3,4}\s*[-.]\s*\d{4}(?!\d)"), "[연락처]"),
    (re.compile(r"(?<!\d)0\d{1,2}\s+\d{3,4}\s+\d{4}(?!\d)"), "[연락처]"),
    (re.compile(r"(?<!\d)01[016789]\d{7,8}(?!\d)"), "[연락처]"),
]


MaskSpan = tuple[int, int, str]   # (시작, 끝, 토큰)


def find_mask_spans(text: str) -> list[MaskSpan]:
    """가릴 구간을 원문 위치로 돌려줍니다. 이름표 규칙이 먼저이고, 겹치는 구간은 앞의 것을 씁니다.
    OCR은 이 구간으로 단어별 글자를 바꾸고 단어 신뢰도는 그대로 둡니다."""
    spans: list[MaskSpan] = []

    def is_free(start: int, end: int) -> bool:
        return all(end <= a or start >= b for a, b, _ in spans)

    for pattern, token in _LABELED_RULES:
        for m in pattern.finditer(text):
            start, end = m.span(3)
            if is_free(start, end):
                spans.append((start, end, token))
    for pattern, token in _SHAPE_RULES:
        for m in pattern.finditer(text):
            start, end = m.span()
            if is_free(start, end):
                spans.append((start, end, token))
    return sorted(spans)


def apply_mask_spans(text: str, spans: list[MaskSpan]) -> str:
    out, pos = [], 0
    for start, end, token in sorted(spans):
        out.append(text[pos:start])
        out.append(token)
        pos = end
    out.append(text[pos:])
    return "".join(out)


def mask_text(text: str) -> str:
    """개인정보를 규칙(정규식)으로 가립니다.

    >>> mask_text("성명: 홍길동 주민등록번호 900101-1234567")
    '성명: [이름] 주민등록번호 [주민번호]'
    """
    if not text:
        return text
    return apply_mask_spans(text, find_mask_spans(text))


# ---------------------------------------------------------------------------
# normalize_drug_name — 약품명 매칭용 정규화 (OCR 매칭·GET /drugs 공용)
# ---------------------------------------------------------------------------
# 숫자 바로 뒤에 오는 단위만 바꿉니다('프로그램'처럼 이름 속 글자는 건드리지 않음).
# 긴 표현부터 검사해야 '밀리그램'이 '그램'으로 먼저 잡히지 않습니다.
_DRUG_UNIT_RULES: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"(\d)\s*(?:밀리\s*그[램람]|mg)"), r"\1mg"),
    (re.compile(r"(\d)\s*(?:마이크로\s*그[램람]|mcg|μg|µg)"), r"\1mcg"),
    (re.compile(r"(\d)\s*(?:밀리\s*리터|ml)"), r"\1ml"),
    (re.compile(r"(\d)\s*(?:그[램람]|g)(?![a-z])"), r"\1g"),
    (re.compile(r"(\d)\s*(?:퍼센트|%)"), r"\1%"),
    (re.compile(r"(\d)\s*(?:국제\s*단위|iu)"), r"\1iu"),
]


# 안쪽에 다른 괄호가 없는 괄호 한 쌍(내용 포함)
_BRACKET_RE = re.compile(r"\([^()]*\)|\[[^\[\]]*\]|\{[^{}]*\}")


def normalize_drug_name(name: str) -> str:
    """처방전 표기와 허가정보 제품명을 같은 모양으로 맞춥니다.

    >>> normalize_drug_name("아모잘탄정5/50밀리그램") == normalize_drug_name("아모잘탄정 5/50mg")
    True
    >>> normalize_drug_name("아모잘탄정 5/50mg")
    '아모잘탄정5/50mg'
    >>> normalize_drug_name("가스모틴정5밀리그램(모사프리드시트르산염수화물)")
    '가스모틴정5mg'

    괄호는 안의 내용까지 지웁니다. 그래서 이름이 같아지는 약이 여러 개일 수 있으니,
    매칭에서는 정확 일치가 1개일 때만 exact, 여러 개면 candidates로 돌려줘야 합니다(6-2).
    """
    if not name:
        return ""
    s = unicodedata.normalize("NFKC", name).lower()   # ㎎→mg, ㎖→ml, 전각 문자 정리
    for pattern, repl in _DRUG_UNIT_RULES:
        s = pattern.sub(repl, s)
    # 괄호는 안의 내용까지 지웁니다. 허가정보 이름 뒤에 붙은 성분명('가스모틴정5밀리그램(모사프리드…)')이
    # 처방전 표기와의 정확 일치를 막기 때문입니다. 괄호 안에 괄호가 있는 이름도 있어서(스티렌투엑스정)
    # 안쪽 괄호부터 더 지울 게 없을 때까지 반복합니다. 짝이 맞지 않는 괄호 기호는 마지막에 기호만 지웁니다.
    prev = None
    while prev != s:
        prev = s
        s = _BRACKET_RE.sub("", s)
    s = re.sub(r"[()\[\]{}]", "", s)
    return re.sub(r"\s+", "", s)
