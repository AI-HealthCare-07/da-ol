"""e약은요(의약품개요정보) API 1페이지 호출 테스트.

- 인증키는 화면에 보이지 않게 입력받습니다(터미널 기록·파일에 남지 않음).
- 환경 변수 DATA_GO_KR_SERVICE_KEY가 있으면 그 값을 씁니다.
- 공공데이터포털 마이페이지의 '일반 인증키(Decoding)'를 넣으세요.
- 표준 라이브러리만 써서 따로 설치할 것이 없습니다.

실행: python3 scripts/drugs/check_easy_drug_api.py
"""

import getpass
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

# 공공데이터포털 '의약품개요정보(e약은요)' 상세 페이지의 요청 주소와 같은지 확인하세요.
BASE_URL = "https://apis.data.go.kr/1471000/DrbEasyDrugInfoService/getDrbEasyDrugList"
NUM_OF_ROWS = 3  # 테스트라 3건만 받아요


def get_service_key() -> str:
    key = os.environ.get("DATA_GO_KR_SERVICE_KEY", "").strip()
    if key:
        return key
    return getpass.getpass("공공데이터포털 인증키(Decoding)를 붙여넣고 Enter (화면에 안 보여요): ").strip()


def main() -> int:
    key = get_service_key()
    if not key:
        print("인증키가 비어 있어요.")
        return 1

    params = {"serviceKey": key, "pageNo": 1, "numOfRows": NUM_OF_ROWS, "type": "json"}
    url = f"{BASE_URL}?{urllib.parse.urlencode(params)}"

    try:
        with urllib.request.urlopen(url, timeout=20) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            print(f"HTTP 상태: {resp.status}")
    except urllib.error.HTTPError as e:
        print(f"HTTP 오류: {e.code} {e.reason}")
        print(e.read().decode("utf-8", errors="replace")[:500])
        return 1
    except urllib.error.URLError as e:
        print(f"연결 오류: {e.reason}")
        return 1

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        # 인증 오류 등은 JSON이 아니라 XML로 오는 경우가 많아요
        print("JSON이 아닌 응답이 왔어요. 앞부분만 보여 드릴게요:")
        print(raw[:500])
        return 1

    header = data.get("header", {})
    body = data.get("body", {})
    print(f"결과 코드: {header.get('resultCode')} / 메시지: {header.get('resultMsg')}")
    print(f"전체 개수(totalCount): {body.get('totalCount')}")

    items = body.get("items") or []
    if isinstance(items, dict):  # 응답 모양이 다를 때 대비
        items = items.get("item", [])
        items = items if isinstance(items, list) else [items]
    print(f"받은 건수: {len(items)}")

    if items:
        print("\n[첫 번째 약의 칸 이름과 값(앞 60자)]")
        for k, v in items[0].items():
            text = "" if v is None else str(v).replace("\n", " ")
            print(f"- {k}: {text[:60]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
