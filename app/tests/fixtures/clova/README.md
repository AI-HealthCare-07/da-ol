# CLOVA General OCR 응답 fixture

`app/services/clova_ocr.py`의 `parse_clova_response()`와 `ClovaOcrClient` 테스트(`app/tests/test_clova_ocr.py`)에 씁니다.

공식 문서(General OCR V2 응답 형식: `images[].fields[]`, `images[].tables[].cells[].cellTextLines[].cellWords[]`)에 맞춰
PR #24 테스트 처방 이미지(`docs/test-prescriptions/`)를 본떠 만든 **예시 응답**입니다. 좌표·신뢰도는 실제 값이 아닙니다.

| 파일 | 본뜬 이미지 | 확인하는 것 |
| --- | --- | --- |
| `case04_table.json` | Case 04 | 표 한 행 = 한 줄, 표 안 글자가 `fields`에도 있어도 한 번만 나옴 |
| `case04_fields_only.json` | Case 04 | 표 인식 없이 `fields`만 있을 때 `lineBreak`로 줄 나누기 |
| `case07_wrapped_cells.json` | Case 07 | 칸 안에서 줄바꿈된 글자('아침 식후 30' / '분')가 한 줄로 이어짐 |
| `case10_low_confidence.json` | Case 10 | 흐린 마지막 줄의 낮은 단어 신뢰도가 그대로 남음 |
| `case11_pill_envelope.json` | Case 11 | 약봉투: 빈 행 건너뛰기, 표 아래 공통 복약안내 줄 |
| `no_text.json` | — | 글자가 거의 없는 사진(`no_text`) |
| `infer_failure.json` | — | `inferResult: FAILURE` |

## 실제 응답으로 바꾸기

CLOVA 키가 생기면 같은 이미지로 실제 응답을 받아 같은 파일 이름으로 바꿔 넣고, `test_clova_ocr.py`의 기대값을 맞춰 주세요.
테스트 처방 이미지는 모두 가상 데이터라 응답을 그대로 저장해도 됩니다. **실제 처방전 응답은 절대 저장하지 않습니다.**

```python
import asyncio, json
from pathlib import Path
from app.services.clova_ocr import ClovaOcrClient

async def dump(image_path: str, out_name: str):
    client = ClovaOcrClient.from_env()
    body = client.build_request_body(Path(image_path).read_bytes())
    resp = await client._http.post(client._url, json=body, headers={"X-OCR-SECRET": client._secret})
    Path(f"app/tests/fixtures/clova/{out_name}").write_text(
        json.dumps(resp.json(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    await client.aclose()

asyncio.run(dump("docs/test-prescriptions/case04.png", "case04_table.json"))
```
