from datetime import date

import pytest

from app.dtos.scan import CycleType, Meal, ParsedBy, Timing
from app.services.instruction_parser import RuleInstructionParser, normalize_instruction

START = date(2026, 11, 24)
B, L, D = Meal.BREAKFAST, Meal.LUNCH, Meal.DINNER
AFTER, BEFORE, BED = Timing.AFTER_MEAL, Timing.BEFORE_MEAL, Timing.BEDTIME


def parse(text, times):
    return RuleInstructionParser().parse(text, times, START)


def shape(dosage):
    return [(d.meal, d.timing, d.offset_min) for d in dosage.doses]


# 테스트 처방(docs/test-prescriptions) 정답값 + 실제 CLOVA에서 쪼개져 나온 글자
@pytest.mark.parametrize(
    "text, times, expected",
    [
        ("아침 식후 30분", 1, [(B, AFTER, 30)]),
        ("저녁 식후 30분", 1, [(D, AFTER, 30)]),
        ("아침·저녁 식후 30분", 2, [(B, AFTER, 30), (D, AFTER, 30)]),
        ("아침 식전 30분", 1, [(B, BEFORE, 30)]),
        ("취침 전", 1, [(None, BED, None)]),
        ("아침·저녁 식후 즉시", 2, [(B, AFTER, 0), (D, AFTER, 0)]),
        # 끼니가 없으면 meal=None (기본 끼니는 fill_default_meals가 채움)
        ("식후 30분", 3, [(None, AFTER, 30)] * 3),
        ("식전 30분", 3, [(None, BEFORE, 30)] * 3),
        ("식후 30분", 2, [(None, AFTER, 30)] * 2),
        # 공백이 쪼개진 OCR 글자 (case11·12 실제 응답, case07)
        ("아침 식후 30 분", 1, [(B, AFTER, 30)]),
        ("식사 후 30분 복용", 3, [(None, AFTER, 30)] * 3),
        ("아침·저녁 식 후 즉시", 2, [(B, AFTER, 0), (D, AFTER, 0)]),
        # 여러 시점
        ("식후 30분, 취침 전", 4, [(None, AFTER, 30)] * 3 + [(None, BED, None)]),
        ("아침저녁 식후30분", 2, [(B, AFTER, 30), (D, AFTER, 30)]),
        ("저녁, 아침 식후 30분", 2, [(B, AFTER, 30), (D, AFTER, 30)]),  # 아침·점심·저녁 순으로
        ("매 식후 30분", 3, [(None, AFTER, 30)] * 3),
        ("자기 전", 1, [(None, BED, None)]),
    ],
)
def test_parsed(text, times, expected):
    d = parse(text, times)
    assert d.parsed_by == ParsedBy.RULE
    assert d.needs_confirm is False, text
    assert d.as_needed is False
    assert shape(d) == expected
    assert [x.dose_no for x in d.doses] == list(range(1, len(expected) + 1))
    assert d.cycle.type == CycleType.DAILY and d.cycle.start_date == START


@pytest.mark.parametrize("text", ["필요시 복용", "통증 시", "필요할 때 1정씩", "PRN"])
def test_as_needed(text):
    d = parse(text, None)
    assert d.as_needed is True and d.doses == []
    if text != "필요할 때 1정씩":
        assert d.needs_confirm is False


def test_times_read_from_text_when_missing():
    d = parse("1일 3회 식후 30분", None)
    assert d.needs_confirm is False and shape(d) == [(None, AFTER, 30)] * 3
    assert len(parse("하루 두 번 식후", None).doses) == 2


@pytest.mark.parametrize(
    "text, times",
    [
        (None, 2),  # 복용 조건 없음
        ("", 2),
        ("1일 2회 복용", 2),  # 시점이 없음 → timing_unknown
        ("환부에 바름", 2),  # 사전에 없는 표현
        ("식후 30분", None),  # 회차 수를 모름
        ("아침·저녁 식후 30분", 3),  # 적힌 끼니 2개 ≠ 1일 3회
        ("1일 2회 식후 30분", 3),  # 글자의 횟수 ≠ 1일 횟수 칸
        ("식후 30분 졸음 주의", 3),  # 읽은 뒤에도 모르는 글자가 남음
    ],
)
def test_needs_confirm(text, times):
    assert parse(text, times).needs_confirm is True


def test_no_instruction_keeps_dose_count():
    d = parse(None, 2)
    assert shape(d) == [(None, None, None)] * 2


@pytest.mark.parametrize(
    "text, timing",
    [
        ("식간", Timing.BETWEEN_MEALS),
        ("공복에 복용", Timing.EMPTY_STOMACH),
        ("8시간마다", Timing.INTERVAL),
    ],
)
def test_unconfirmed_timings(text, timing):
    d = parse(text, 3)
    assert d.needs_confirm is True
    assert [x.timing for x in d.doses] == [timing] * 3


@pytest.mark.parametrize(
    "text, cycle",
    [
        ("격일 아침 식후 30분", CycleType.EVERY_OTHER_DAY),
        ("주 1회 아침 식전", CycleType.WEEKLY),
    ],
)
def test_unconfirmed_cycles(text, cycle):
    d = parse(text, 1)
    assert d.cycle.type == cycle and d.needs_confirm is True


def test_normalize_removes_spaces_and_synonyms():
    assert normalize_instruction("식사 후  30 분") == "식후30분"
    assert normalize_instruction("잠 자기 전") == "취침전"
    assert normalize_instruction("１일 ３회") == "1일3회"  # 전각 숫자


def test_same_input_same_output():
    assert parse("아침·저녁 식후 30분", 2) == parse("아침·저녁 식후 30분", 2)
