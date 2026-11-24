"""의약품 제품 허가정보 전체를 받아 JSON 파일로 저장.

- 인증키는 화면에 보이지 않게 입력받습니다(터미널 기록·파일에 남지 않음).
- 환경 변수 DATA_GO_KR_SERVICE_KEY가 있으면 그 값을 씁니다.
- 공공데이터포털 마이페이지의 '일반 인증키(Decoding)'를 넣으세요.
- 표준 라이브러리만 써서 따로 설치할 것이 없습니다.

실행: python3 scripts/drugs/fetch_permit_all.py
"""

import getpass
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path

# 공공데이터포털 '의약품 제품 허가정보' 목록 기능의 요청 주소와 같은지 확인하세요.
BASE_URL = "https://apis.data.go.kr/1471000/DrugPrdtPrmsnInfoService08/getDrugPrdtPrmsnInq08"
NUM_OF_ROWS = 100
SAVE_DIR = Path.home() / "Documents" / "final_project" / "data" / "raw"


def get_service_key() -> str:
    key = os.environ.get("DATA_GO_KR_SERVICE_KEY", "").strip()
    if key:
        return key
    return getpass.getpass("공공데이터포털 인증키(Decoding)를 붙여넣고 Enter (화면에 안 보여요): ").strip()


def fetch_page(key: str, page_no: int) -> dict:
    params = {"serviceKey": key, "pageNo": page_no, "numOfRows": NUM_OF_ROWS, "type": "json"}
    url = f"{BASE_URL}?{urllib.parse.urlencode(params)}"
    with urllib.request.urlopen(url, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def get_items(body: dict) -> list:
    items = body.get("items") or []
    if isinstance(items, dict):
        items = items.get("item", [])
        items = items if isinstance(items, list) else [items]
    return items


def main() -> int:
    key = get_service_key()
    first = fetch_page(key, 1)
    total = int(first["body"]["totalCount"])
    last_page = (total + NUM_OF_ROWS - 1) // NUM_OF_ROWS
    print(f"전체 {total}건, {last_page}페이지를 받아요.")

    all_items = get_items(first["body"])
    for page_no in range(2, last_page + 1):
        time.sleep(0.3)
        try:
            data = fetch_page(key, page_no)
        except (urllib.error.URLError, json.JSONDecodeError) as e:
            print(f"{page_no}페이지에서 멈췄어요: {e}")
            break
        all_items.extend(get_items(data["body"]))
        print(f"{page_no}/{last_page}페이지 완료 (누적 {len(all_items)}건)")

    SAVE_DIR.mkdir(parents=True, exist_ok=True)
    out = SAVE_DIR / f"permit_{date.today():%Y%m%d}.json"
    out.write_text(json.dumps(all_items, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"저장 완료: {out} ({len(all_items)}건 / 전체 {total}건)")
    return 0 if len(all_items) == total else 1


if __name__ == "__main__":
    sys.exit(main())
