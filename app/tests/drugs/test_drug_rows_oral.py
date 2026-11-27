"""build_drug_rows.guess_is_oral() 테스트. 성상(CHART) 문구는 허가 상세정보에서 가져온 실제 예시예요."""

import pytest

from scripts.drugs.build_drug_rows import guess_is_oral


@pytest.mark.parametrize(
    ("name", "chart", "expected"),
    [
        # 먹는 약 → True
        ("아모잘탄정5/50밀리그램", "흰색의 장방형 필름코팅 정제", True),
        ("코대원포르테시럽", "플라스틱병 또는 알루미늄 호일 파우치에 든 빨간색의 방향성 시럽", True),
        ("알마겔정(알마게이트)(수출명:유한가스트라겔정)", "백색의 원형 정제", True),
        # 안 먹는 약 → False
        ("히알유니점안액0.15%(히알루론산나트륨)", "무색투명한 액이 무색투명한 플라스틱용기에 든 점안제", False),
        ("에스로반연고(무피로신)", "엷은 흰색의 전질균등한 연고", False),
        ("대한포도당주사액(10%)", "단맛이 있는 무색투명한 액을 유리 또는 플라스틱 용기에 충진한 것", False),
        # 헷갈리면 None (먹는 약을 False로 막지 않기)
        ("뉴헴시럽(수출용)", "감미와 산미가 있는 암갈색의 시럽이 든 앰플제", None),
        ("익셀캡슐12.5밀리그램(밀나시프란염산염)", "흰색 내지 크림흰색의 분말이 든 상하 연갈색 불투명 경질캡슐", None),
        ("발포비타정", "원형 정제로 물에 넣으면 탄산가스를 발생하는 발포정", None),
        ("동구치모모둘린시럽(수출용)", "갈색 투명한 바이알 또는 병에 든 미황색 투명한 액", None),
        ("가상액", "무색의 투명한 액", None),
    ],
)
def test_guess_is_oral(name, chart, expected):
    assert guess_is_oral(name, chart) is expected
