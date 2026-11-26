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

## 실제 응답 (`real/`)

위 예시 fixture는 파싱 규칙을 정확히 통제해서 확인하는 용도라 그대로 둡니다.
실제 CLOVA 응답은 `real/caseNN.json`에 따로 두고 `test_clova_real.py`에서 확인합니다
(줄 번호·단어 위치, 약 이름, 실제 응답에서의 마스킹).

| 파일 | 이미지 |
| --- | --- |
| `real/case04.json` | Case 04 처방전(표) |
| `real/case07.json` | Case 07 칸 안 줄바꿈 |
| `real/case10.json` | Case 10 흐린 줄 |
| `real/case11.json` | Case 11 약봉투 (`김다올 님 귀하`) |
| `real/case12.json` | Case 12 마스킹 (두 줄로 나뉜 연락처) |

실제 응답은 `scripts/ocr/run_clova_test_prescriptions.py --save-raw`로 받은 `caseNN_clova_raw.json`을 복사합니다.
테스트 처방 이미지는 모두 가상 데이터라 응답을 그대로 저장해도 됩니다. **실제 처방전 응답은 절대 저장하지 않습니다.**
