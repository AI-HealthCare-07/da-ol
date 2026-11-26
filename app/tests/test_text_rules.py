import pytest

from app.services.text_rules import mask_text, normalize_drug_name, parse_dose_text


@pytest.mark.parametrize(
    "text, expected",
    [
        ("1/2정", (0.5, 0.5, "정")),
        ("1정", (1.0, 1.0, "정")),
        ("1정씩", (1.0, 1.0, "정")),
        ("반정", (0.5, 0.5, "정")),
        ("1~2정", (1.0, 2.0, "정")),
        ("1 캡슐", (1.0, 1.0, "캡슐")),
        ("5mL", (5.0, 5.0, "mL")),
        ("5ml", (5.0, 5.0, "mL")),
        ("1포", (1.0, 1.0, "포")),
        ("0.5T", (0.5, 0.5, "정")),
        ("１정", (1.0, 1.0, "정")),  # 전각 숫자
    ],
)
def test_parse_ok(text, expected):
    r = parse_dose_text(text)
    assert r["parsed"] is True
    assert (r["min"], r["max"], r["unit"]) == expected
    assert r["text"] == text


@pytest.mark.parametrize("text", ["적당량", "", "   ", "정", "2~1정", "0정", "1/0정", "1회"])
def test_parse_fail(text):
    r = parse_dose_text(text)
    assert r == {"text": text, "min": None, "max": None, "unit": None, "parsed": False}


def test_parse_deterministic():
    assert parse_dose_text("1/2정") == parse_dose_text("1/2정")


@pytest.mark.parametrize(
    "text, expected",
    [
        ("성명: 홍길동", "성명: [이름]"),
        ("환자성명 김가상", "환자성명 [이름]"),
        ("900101-1234567", "[주민번호]"),
        ("900101 - 1******", "[주민번호]"),
        ("9001011234567", "[주민번호]"),
        ("연락처 010-1234-5678", "연락처 [연락처]"),
        ("02)123-4567", "[연락처]"),
        ("01012345678", "[연락처]"),
        ("a.b@test.com 으로", "[이메일] 으로"),
        ("환자번호: 12345678", "환자번호: [환자번호]"),
        ("면허번호 54321", "면허번호 [면허번호]"),
        ("주민등록번호 900101-1234567", "주민등록번호 [주민번호]"),
        ("등록번호 A-1234", "등록번호 [환자번호]"),
        ("900101 1234567", "[주민번호]"),  # 챗봇에서 띄어 쓴 경우
        ("연락처 010 1234 5678", "연락처 [연락처]"),
        ("02 123 4567로 전화", "[연락처]로 전화"),
    ],
)
def test_mask(text, expected):
    assert mask_text(text) == expected


def test_mask_keeps_dose_text():
    # 약 줄의 숫자는 가리면 안 됩니다
    line = "가상정5mg 1 3 5 식후30분"
    assert mask_text(line) == line


@pytest.mark.parametrize(
    "text",
    [
        "혈압 130 85 정도예요",
        "10 20mg 먹어도 되나요",
        "2026 11 25 처방",
        "가상정5mg 1 3 5 식후30분",
    ],
)
def test_mask_keeps_spaced_numbers(text):
    # 띄어 쓴 번호 규칙이 일반 숫자를 가리면 안 됩니다
    assert mask_text(text) == text


def test_mask_name_only_with_label():
    # 이름표가 없는 이름은 1차에서 가리지 않습니다(6-4)
    assert mask_text("홍길동님 약 먹어도 되나요") == "홍길동님 약 먹어도 되나요"


@pytest.mark.parametrize(
    "permit, rx",
    [
        ("아모잘탄정5/50밀리그램", "아모잘탄정 5/50mg"),
        ("타이레놀정500밀리그람", "타이레놀정 500 mg"),
        ("가상정2.5밀리그램", "가상정 2.5㎎"),
        ("가상정0.25마이크로그램", "가상정 0.25mcg"),
        ("가상시럽100밀리리터", "가상시럽 100mL"),
        ("가상산1그램", "가상산 1g"),
        ("가상크림1퍼센트", "가상크림 1%"),
        ("가상정5/50MG", "가상정 5/50mg"),
        ("가상정(가상성분)5밀리그램", "가상정 5mg"),  # 괄호 안 내용까지 지움
        ("가스모틴정5밀리그램(모사프리드시트르산염수화물)", "가스모틴정 5mg"),
        ("스티렌투엑스정(애엽95%에탄올연조엑스(20→1))", "스티렌투엑스정"),  # 괄호 안에 괄호
        ("무코스타정(레바미피드)", "무코스타정"),
    ],
)
def test_normalize_drug_name_same(permit, rx):
    assert normalize_drug_name(permit) == normalize_drug_name(rx)


@pytest.mark.parametrize(
    "name, expected",
    [
        ("아모잘탄정 5/50mg", "아모잘탄정5/50mg"),
        ("가상 캡슐", "가상캡슐"),
        ("프로그램정", "프로그램정"),  # 숫자 뒤가 아닌 '그램'은 그대로
        ("가상정[가상(성분)]5mg", "가상정5mg"),  # 종류가 다른 괄호가 겹친 경우
        ("가상정(5mg", "가상정5mg"),  # 짝이 안 맞는 괄호는 기호만 지움
        ("", ""),
    ],
)
def test_normalize_drug_name_values(name, expected):
    assert normalize_drug_name(name) == expected


def test_strength_differs_stays_different():
    assert normalize_drug_name("아모잘탄정5/50밀리그램") != normalize_drug_name("아모잘탄정 5/100mg")


# 약봉투 '귀하' 앞 이름 (실제 CLOVA 응답 case11: '김다올 님 귀하')
@pytest.mark.parametrize(
    "text, expected",
    [
        ("김다올 님 귀하 (비식별 샘플)", "[이름] 님 귀하 (비식별 샘플)"),
        ("김다올님 귀하", "[이름]님 귀하"),
        ("김다올님귀하", "[이름]님귀하"),
        ("김다올 귀하", "[이름] 귀하"),
        ("김다올귀하", "[이름]귀하"),
    ],
)
def test_mask_name_before_gwiha(text, expected):
    assert mask_text(text) == expected


@pytest.mark.parametrize("text", ["약사님 확인", "조제약사", "귀하의 건강을 위해"])
def test_gwiha_rule_does_not_overmask(text):
    assert mask_text(text) == text
