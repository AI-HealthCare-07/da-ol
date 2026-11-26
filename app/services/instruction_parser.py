"""복용 조건 표현 사전 (scan_service.InstructionParser 구현) — 담당: AI A 채민

복용 조건 글자('아침·저녁 식후 30분', '취침 전', '필요시 복용')를 Dosage로 바꿉니다(명세서 6-2 dosage 표).

원칙
- 1차는 사전(규칙)만 씁니다. 결과는 항상 parsed_by=rule이고, LLM 해석은 2차입니다.
- 비교 전에 공백을 모두 지웁니다. OCR이 좁은 칸에서 글자를 쪼개도('식 후 30 분') 같은 표현으로 읽습니다.
- 끼니가 적혀 있지 않으면 meal=None으로 둡니다. 기본 끼니는 fill_default_meals()(4장, 민정)가 채웁니다.
- 아래 경우는 needs_confirm=True ("복용 조건을 확인해 주세요"):
  · 사전에 없는 글자가 남음(일부만 읽은 경우도 포함)
  · 1차에서 계산하지 않는 조건: 식간·공복·N시간마다, 격일·매주
  · 회차 수를 알 수 없거나, 적힌 끼니 수·1일 횟수가 서로 맞지 않음
- 필요시 약은 as_needed=True, doses=[]이고 시간표·알림에서 빠집니다(MED-008).

DB·외부 호출이 없는 순수 함수입니다. 같은 입력이면 항상 같은 결과입니다.
"""

from __future__ import annotations

import re
import unicodedata
from datetime import date

from app.dtos.scan import Cycle, CycleType, Dosage, Dose, Meal, ParsedBy, Timing

INSTRUCTION_DICT_VERSION = "instruction_dict_v1"

# ---------------------------------------------------------------------------
# 사전 (공백을 지운 글자 기준). 테스트하면서 늘립니다.
# ---------------------------------------------------------------------------
# 같은 뜻의 다른 표기 → 기준 표기 (긴 표현부터 바꿉니다)
_SYNONYMS: list[tuple[str, str]] = [
    ("식사직후", "식후즉시"),
    ("식사바로후", "식후즉시"),
    ("식사후", "식후"),
    ("식사전", "식전"),
    ("식사사이", "식간"),
    ("잠자기전", "취침전"),
    ("잠들기전", "취침전"),
    ("자기전", "취침전"),
    ("취침시", "취침전"),
    ("빈속", "공복"),
]

_MEAL_WORDS: dict[str, Meal] = {
    "아침": Meal.BREAKFAST,
    "조식": Meal.BREAKFAST,
    "점심": Meal.LUNCH,
    "중식": Meal.LUNCH,
    "저녁": Meal.DINNER,
    "석식": Meal.DINNER,
}
_MEAL_ORDER = [Meal.BREAKFAST, Meal.LUNCH, Meal.DINNER]

_TIMING_WORDS: dict[str, Timing] = {
    "식후": Timing.AFTER_MEAL,
    "식전": Timing.BEFORE_MEAL,
    "식간": Timing.BETWEEN_MEALS,
    "공복": Timing.EMPTY_STOMACH,
    "취침전": Timing.BEDTIME,
}
# 1차에서 시간표를 계산하지 않는 시점 → needs_confirm
_UNCONFIRMED_TIMINGS = {Timing.BETWEEN_MEALS, Timing.EMPTY_STOMACH, Timing.INTERVAL}
_MEAL_BASED = {Timing.AFTER_MEAL, Timing.BEFORE_MEAL, Timing.BETWEEN_MEALS}

_KOREAN_COUNTS = {"한": 1, "두": 2, "세": 3, "네": 4}

_MEAL_RE = "|".join(_MEAL_WORDS)
_TIMING_RE = "|".join(sorted(_TIMING_WORDS, key=len, reverse=True))
# 끼니(여러 개 가능) + 시점 + 분/즉시. 예: 아침·저녁식후30분, 매식전30분, 취침전
_CLAUSE_RE = re.compile(
    rf"(?P<meals>(?:{_MEAL_RE})(?:[·,./및와과]?(?:{_MEAL_RE}))*)?"
    rf"매?(?P<timing>{_TIMING_RE})"
    r"(?:(?P<min>\d{1,3})분(?:후|전|이내|뒤)?|(?P<now>즉시|직후|바로))?"
)
_TIMES_RE = re.compile(r"(?:1일|하루)(?P<n>\d|한|두|세|네)(?:회|번)")
_AS_NEEDED_RE = re.compile(r"필요시|필요할때|필요한경우|통증시|아플때|발열시|열날때|prn", re.IGNORECASE)
_INTERVAL_RE = re.compile(r"\d{1,2}시간(?:마다|간격)")
_EVERY_OTHER_DAY_RE = re.compile(r"격일|이틀에?한번|2일마다|하루걸러")
_WEEKLY_RE = re.compile(r"매주|주\d회|일주일에?(?:한|\d)(?:번|회)")
# 뜻 없이 붙는 말·기호. 지우고도 글자가 남으면 사전에 없는 표현이 있다는 뜻
_FILLER_RE = re.compile(r"복용|투여|투약|드세요|드십시오|하세요|하십시오|합니다|씩|각|매|및|에|[·,./()\[\]\-~:;]")


def normalize_instruction(text: str) -> str:
    """전각 문자를 맞추고 공백을 모두 지운 뒤 같은 뜻의 표기를 기준 표기로 바꿉니다."""
    s = "".join(unicodedata.normalize("NFKC", text).split())
    for old, new in _SYNONYMS:
        s = s.replace(old, new)
    return s


def _times_in_text(s: str) -> int | None:
    m = _TIMES_RE.search(s)
    if not m:
        return None
    n = m.group("n")
    return _KOREAN_COUNTS.get(n) or int(n)


def _fallback(times: int | None, start_date: date) -> Dosage:
    """사전으로 못 읽음: 회차만 만들고 끼니·시점은 비워 둠(scan_service.fallback_dosage와 같은 모양)."""
    return Dosage(
        parsed_by=ParsedBy.RULE,
        needs_confirm=True,
        as_needed=False,
        doses=[Dose(dose_no=i + 1, meal=None, timing=None, offset_min=None) for i in range(times or 0)],
        cycle=Cycle(type=CycleType.DAILY, start_date=start_date),
    )


def _offset(m: re.Match[str], timing: Timing) -> int | None:
    if timing not in _MEAL_BASED:
        return None
    if m.group("min"):
        return int(m.group("min"))
    if m.group("now"):
        return 0
    return None


def _meals_of(group: str | None) -> list[Meal]:
    if not group:
        return []
    found = [_MEAL_WORDS[w] for w in re.findall(_MEAL_RE, group)]
    return [meal for meal in _MEAL_ORDER if meal in found]  # 중복 제거 + 아침·점심·저녁 순


_DoseSpec = tuple[Meal | None, Timing, int | None]


def _read_cycle(s: str) -> CycleType:
    if _EVERY_OTHER_DAY_RE.search(s):
        return CycleType.EVERY_OTHER_DAY
    if _WEEKLY_RE.search(s):
        return CycleType.WEEKLY
    return CycleType.DAILY


def _collect(clauses: list[re.Match[str]]) -> tuple[list[_DoseSpec], list[tuple[Timing, int | None]], int, bool]:
    """읽은 구절을 끼니가 적힌 회차·끼니 없는 식전·식후·취침 전으로 나눕니다. 마지막 값은 확인 필요 여부."""
    fixed: list[_DoseSpec] = []
    generic: list[tuple[Timing, int | None]] = []
    bedtime = 0
    unconfirmed = False
    for m in clauses:
        timing = _TIMING_WORDS[m.group("timing")]
        offset = _offset(m, timing)
        meals = _meals_of(m.group("meals"))
        unconfirmed = unconfirmed or timing in _UNCONFIRMED_TIMINGS
        if timing == Timing.BEDTIME:
            bedtime += 1
        elif meals:
            fixed += [(meal, timing, offset) for meal in meals]
        else:
            generic.append((timing, offset))
    return fixed, generic, bedtime, unconfirmed


def _arrange(
    fixed: list[_DoseSpec], generic: list[tuple[Timing, int | None]], bedtime: int, times: int | None
) -> tuple[list[_DoseSpec], bool]:
    """회차 순서(아침·점심·저녁, 끼니 모름, 취침 전)로 놓습니다. 두 번째 값은 회차 수가 맞지 않아 확인 필요한지."""
    specs = list(fixed)
    unsure = False
    if generic:
        # '식후 30분'처럼 끼니가 없으면 남은 회차를 모두 그 시점으로. 회차 수를 모르면 확인 필요
        remaining = (times - len(fixed) - bedtime) if times else 0
        unsure = remaining <= 0 or len(generic) > 1
        timing, offset = generic[0]
        specs += [(None, timing, offset)] * max(remaining, 0)
    specs.sort(key=lambda d: _MEAL_ORDER.index(d[0]) if d[0] else len(_MEAL_ORDER))
    specs += [(None, Timing.BEDTIME, None)] * bedtime
    if times and len(specs) != times:
        unsure = True
    return specs, unsure


def _dosage(needs_confirm: bool, specs: list[_DoseSpec], cycle: Cycle, *, as_needed: bool = False) -> Dosage:
    doses = [
        Dose(dose_no=i + 1, meal=meal, timing=timing, offset_min=off) for i, (meal, timing, off) in enumerate(specs)
    ]
    return Dosage(parsed_by=ParsedBy.RULE, needs_confirm=needs_confirm, as_needed=as_needed, doses=doses, cycle=cycle)


class RuleInstructionParser:
    """scan_service.InstructionParser 구현 (parsed_by=rule)."""

    def parse(self, instruction_text: str | None, times_per_day: int | None, start_date: date) -> Dosage:
        s = normalize_instruction(instruction_text or "")
        text_times = _times_in_text(s)
        times = times_per_day or text_times
        cycle = Cycle(type=_read_cycle(s), start_date=start_date)
        # 글자의 횟수와 1일 횟수 칸이 다르거나, 1차 미계산 주기(격일·매주)면 확인 필요
        needs_confirm = bool(times_per_day and text_times and times_per_day != text_times)
        needs_confirm = needs_confirm or cycle.type != CycleType.DAILY

        rest = s
        for pattern in (_TIMES_RE, _EVERY_OTHER_DAY_RE, _WEEKLY_RE):
            rest = pattern.sub("", rest)

        if _AS_NEEDED_RE.search(rest):  # 필요시: 회차 없음
            leftover = _FILLER_RE.sub("", _AS_NEEDED_RE.sub("", rest))
            return _dosage(needs_confirm or bool(leftover), [], cycle, as_needed=True)
        if _INTERVAL_RE.search(rest):  # N시간마다: 1차 미계산
            return _dosage(True, [(None, Timing.INTERVAL, None)] * (times or 0), cycle)

        clauses = list(_CLAUSE_RE.finditer(rest))
        if not clauses:
            return _fallback(times, start_date).model_copy(update={"cycle": cycle})

        leftover = _FILLER_RE.sub("", _CLAUSE_RE.sub("", rest))
        fixed, generic, bedtime, unconfirmed = _collect(clauses)
        specs, unsure = _arrange(fixed, generic, bedtime, times)
        return _dosage(needs_confirm or bool(leftover) or unconfirmed or unsure, specs, cycle)
