# 공용 테스트 처방 시나리오 (전체 13건 — 필수 10건 + 선택 3건)

> 작성자: 이재경
> 기준 스키마: `daol_API_명세서.md` 6장 `GET /scans/{scan_id}` & `POST /scans/{scan_id}/confirm` Request Body
> 구성: 정상 6건 + 함정 4건 + 선택 확장 3건(약봉투 · 개인정보 마스킹 · 비경구약 거절)
> 참고 사항:
> - 본 문서의 `drug_id`(1001~1026)는 공공데이터(`drugs`) 적재 전 **예시 ID**입니다. 실제 테스트 비교 시에는 `drug_name`(`item_name`) 또는 품목기준코드 기준으로 대조해 주세요.
> - 각 약품 항목의 `raw_text`는 `GET /scans/{scan_id}` 단계에서 추출·마스킹된 원문 줄이며, 표현 사전 테스트용으로 함께 기재했습니다.

| 번호 | 구분 | 유형 | 문서 종류 | 이미지 | 약품 수 |
| --- | --- | --- | --- | --- | --- |
| Case 01 | 정상 1 | 고혈압·이상지질혈증 정기 처방 | `prescription` | `./case01.png` | 2개 |
| Case 02 | 정상 2 | 당뇨·위장보호 복합 처방 | `prescription` | `./case02.png` | 2개 |
| Case 03 | 함정 1 | 끼니 안 적힌 1일 2회 | `prescription` | `./case03.png` | 2개 |
| Case 04 | 정상 3 | 급성 기관지염·감기 시럽·정제 처방 | `prescription` | `./case04.png` | 3개 |
| Case 05 | 정상 4 | 식전·취침 전 복용 조건 포함 처방 | `prescription` | `./case05.png` | 3개 |
| Case 06 | 정상 5 | 필요시(PRN) 복용 약 포함 처방 | `prescription` | `./case06.png` | 2개 |
| Case 07 | 정상 6 | 만성질환 다제약물(4종) 복합 처방 | `prescription` | `./case07.png` | 4개 |
| Case 08 | 함정 2 | 공공데이터에 없는 약 이름 | `prescription` | `./case08.png` | 2개 |
| Case 09 | 함정 3 | 비정상·오인식 용량 (`10정`) | `prescription` | `./case09.png` | 2개 |
| Case 10 | 함정 4 | 마지막 줄 약 하나 빠짐 주의 처방 | `prescription` | `./case10.png` | 3개 |
| Case 11 | 선택 1 | 약봉투(`pill_bag`) 포맷 인식 | `pill_bag` | `./case11.png` | 2개 |
| Case 12 | 선택 2 | 가상 개인정보 마스킹(`mask_text()`) 확인 | `prescription` | `./case12.png` | 2개 |
| Case 13 | 선택 3 | 비경구약(`is_oral: false`) 거절 확인 | `prescription` | `./case13.png` | 2개 |

---

## Case 01 [정상 1] 고혈압·이상지질혈증 정기 처방
- **예시 이미지:** `./case01.png` (`document_type: "prescription"`)
- **약 목록 요약:**
  1. `아모잘탄정 5/50mg` | 1회 용량: `1정` | 1일 횟수: `1회` | 총 일수: `30일` | 복용 조건: `아침 식후 30분`
  2. `리바로정 2mg` | 1회 용량: `1정` | 1일 횟수: `1회` | 총 일수: `30일` | 복용 조건: `저녁 식후 30분`
- **정답값 (`POST /scans/{scan_id}/confirm` Request Body & `raw_text` 기준):**
  ```json
  {
    "hospital_name": "다올내과의원",
    "prescribed_date": "2026-11-20",
    "drugs": [
      {
        "line_no": 1,
        "raw_text": "아모잘탄정 5/50mg 1정 1회 30일 아침 식후 30분",
        "drug_id": 1001,
        "drug_name": "아모잘탄정 5/50mg",
        "dose_per_time": { "text": "1정", "min": 1, "max": 1, "unit": "정", "parsed": true },
        "times_per_day": 1,
        "total_days": 30,
        "instruction_text": "아침 식후 30분",
        "dosage": {
          "parsed_by": "rule",
          "as_needed": false,
          "doses": [
            { "dose_no": 1, "meal": "breakfast", "timing": "after_meal", "offset_min": 30 }
          ],
          "cycle": { "type": "daily", "start_date": "2026-11-20" }
        }
      },
      {
        "line_no": 2,
        "raw_text": "리바로정 2mg 1정 1회 30일 저녁 식후 30분",
        "drug_id": 1002,
        "drug_name": "리바로정 2mg",
        "dose_per_time": { "text": "1정", "min": 1, "max": 1, "unit": "정", "parsed": true },
        "times_per_day": 1,
        "total_days": 30,
        "instruction_text": "저녁 식후 30분",
        "dosage": {
          "parsed_by": "rule",
          "as_needed": false,
          "doses": [
            { "dose_no": 1, "meal": "dinner", "timing": "after_meal", "offset_min": 30 }
          ],
          "cycle": { "type": "daily", "start_date": "2026-11-20" }
        }
      }
    ]
  }
  ```
- **기대 동작:** 2개 약물 모두 정상 매칭, 확정 시 `conditions_to_confirm: []` (추가 확인 필요 항목 없음)

---

## Case 02 [정상 2] 당뇨·위장보호 복합 처방
- **예시 이미지:** `./case02.png` (`document_type: "prescription"`)
- **약 목록 요약:**
  1. `자누메트정 50/500mg` | 1회 용량: `1정` | 1일 횟수: `2회` | 총 일수: `30일` | 복용 조건: `아침·저녁 식후 30분`
  2. `알마겔정` | 1회 용량: `1정` | 1일 횟수: `3회` | 총 일수: `14일` | 복용 조건: `식후 30분`
- **정답값 (`POST /scans/{scan_id}/confirm` Request Body & `raw_text` 기준):**
  ```json
  {
    "hospital_name": "현풍연합내과",
    "prescribed_date": "2026-11-20",
    "drugs": [
      {
        "line_no": 1,
        "raw_text": "자누메트정 50/500mg 1정 2회 30일 아침·저녁 식후 30분",
        "drug_id": 1003,
        "drug_name": "자누메트정 50/500mg",
        "dose_per_time": { "text": "1정", "min": 1, "max": 1, "unit": "정", "parsed": true },
        "times_per_day": 2,
        "total_days": 30,
        "instruction_text": "아침·저녁 식후 30분",
        "dosage": {
          "parsed_by": "rule",
          "as_needed": false,
          "doses": [
            { "dose_no": 1, "meal": "breakfast", "timing": "after_meal", "offset_min": 30 },
            { "dose_no": 2, "meal": "dinner", "timing": "after_meal", "offset_min": 30 }
          ],
          "cycle": { "type": "daily", "start_date": "2026-11-20" }
        }
      },
      {
        "line_no": 2,
        "raw_text": "알마겔정 1정 3회 14일 식후 30분",
        "drug_id": 1004,
        "drug_name": "알마겔정",
        "dose_per_time": { "text": "1정", "min": 1, "max": 1, "unit": "정", "parsed": true },
        "times_per_day": 3,
        "total_days": 14,
        "instruction_text": "식후 30분",
        "dosage": {
          "parsed_by": "rule",
          "as_needed": false,
          "doses": [
            { "dose_no": 1, "meal": "breakfast", "timing": "after_meal", "offset_min": 30 },
            { "dose_no": 2, "meal": "lunch", "timing": "after_meal", "offset_min": 30 },
            { "dose_no": 3, "meal": "dinner", "timing": "after_meal", "offset_min": 30 }
          ],
          "cycle": { "type": "daily", "start_date": "2026-11-20" }
        }
      }
    ]
  }
  ```
- **기대 동작:** 약물별 상이한 총 일수(`30일` / `14일`) 및 1일 2회·3회 식후 조건 정확 분리, `conditions_to_confirm: []`

---

## Case 03 [함정 1 — 끼니 안 적힌 1일 2회] 위장약 처방
- **예시 이미지:** `./case03.png` (`document_type: "prescription"`)
- **함정 포인트:** `넥시움정 20mg`의 용법란에 끼니(아침/점심/저녁) 및 식전·식후 조건 없이 `1일 2회 복용`만 기재된 경우
- **`GET /scans/{scan_id}` 단계(수정 전) 기대값:**
  - `drugs[0]` (`넥시움정 20mg`): `dosage.needs_confirm: true`, `dosage.doses: [{ "dose_no": 1, "meal": null, "timing": null, "offset_min": null }, { "dose_no": 2, "meal": null, "timing": null, "offset_min": null }]`
  - `drugs[1]` (`무코스타정`): `dosage.needs_confirm: false`
- **확정 정답값 (`POST /scans/{scan_id}/confirm` Request Body & `raw_text` 기준):**
  ```json
  {
    "hospital_name": "달성가정의학과",
    "prescribed_date": "2026-11-20",
    "drugs": [
      {
        "line_no": 1,
        "raw_text": "넥시움정 20mg 1정 2회 14일 1일 2회 복용",
        "drug_id": 1005,
        "drug_name": "넥시움정 20mg",
        "dose_per_time": { "text": "1정", "min": 1, "max": 1, "unit": "정", "parsed": true },
        "times_per_day": 2,
        "total_days": 14,
        "instruction_text": "1일 2회 복용",
        "dosage": {
          "parsed_by": "rule",
          "as_needed": false,
          "doses": [
            { "dose_no": 1, "meal": null, "timing": null, "offset_min": null },
            { "dose_no": 2, "meal": null, "timing": null, "offset_min": null }
          ],
          "cycle": { "type": "daily", "start_date": "2026-11-20" }
        }
      },
      {
        "line_no": 2,
        "raw_text": "무코스타정 1정 3회 14일 식후 30분",
        "drug_id": 1006,
        "drug_name": "무코스타정",
        "dose_per_time": { "text": "1정", "min": 1, "max": 1, "unit": "정", "parsed": true },
        "times_per_day": 3,
        "total_days": 14,
        "instruction_text": "식후 30분",
        "dosage": {
          "parsed_by": "rule",
          "as_needed": false,
          "doses": [
            { "dose_no": 1, "meal": "breakfast", "timing": "after_meal", "offset_min": 30 },
            { "dose_no": 2, "meal": "lunch", "timing": "after_meal", "offset_min": 30 },
            { "dose_no": 3, "meal": "dinner", "timing": "after_meal", "offset_min": 30 }
          ],
          "cycle": { "type": "daily", "start_date": "2026-11-20" }
        }
      }
    ]
  }
  ```
- **확정 후 기대 동작:** `meal: null`, `timing: null` 상태로 확정 시 `POST /scans/{scan_id}/confirm` 응답의 `conditions_to_confirm` 배열에 `넥시움정 20mg`의 1·2회차(`dose_no: 1, 2`)가 `timing_unknown` 사유로 반환되어 사용자 선택(`PATCH /dose-conditions/{condition_id}`) 유도

---

## Case 04 [정상 3] 급성 기관지염·감기 시럽·정제 처방
- **예시 이미지:** `./case04.png` (`document_type: "prescription"`)
- **약 목록 요약:**
  1. `코대원포르테시럽` | 1회 용량: `20mL` | 1일 횟수: `3회` | 총 일수: `3일` | 복용 조건: `식후 30분`
  2. `펠루비정` | 1회 용량: `1정` | 1일 횟수: `3회` | 총 일수: `3일` | 복용 조건: `식후 30분`
  3. `무코스타정` | 1회 용량: `1정` | 1일 횟수: `3회` | 총 일수: `3일` | 복용 조건: `식후 30분`
- **정답값 (`POST /scans/{scan_id}/confirm` Request Body & `raw_text` 기준):**
  ```json
  {
    "hospital_name": "논공이비인후과",
    "prescribed_date": "2026-11-24",
    "drugs": [
      {
        "line_no": 1,
        "raw_text": "코대원포르테시럽 20mL 3회 3일 식후 30분",
        "drug_id": 1007,
        "drug_name": "코대원포르테시럽",
        "dose_per_time": { "text": "20mL", "min": 20, "max": 20, "unit": "mL", "parsed": true },
        "times_per_day": 3,
        "total_days": 3,
        "instruction_text": "식후 30분",
        "dosage": {
          "parsed_by": "rule",
          "as_needed": false,
          "doses": [
            { "dose_no": 1, "meal": "breakfast", "timing": "after_meal", "offset_min": 30 },
            { "dose_no": 2, "meal": "lunch", "timing": "after_meal", "offset_min": 30 },
            { "dose_no": 3, "meal": "dinner", "timing": "after_meal", "offset_min": 30 }
          ],
          "cycle": { "type": "daily", "start_date": "2026-11-24" }
        }
      },
      {
        "line_no": 2,
        "raw_text": "펠루비정 1정 3회 3일 식후 30분",
        "drug_id": 1008,
        "drug_name": "펠루비정",
        "dose_per_time": { "text": "1정", "min": 1, "max": 1, "unit": "정", "parsed": true },
        "times_per_day": 3,
        "total_days": 3,
        "instruction_text": "식후 30분",
        "dosage": {
          "parsed_by": "rule",
          "as_needed": false,
          "doses": [
            { "dose_no": 1, "meal": "breakfast", "timing": "after_meal", "offset_min": 30 },
            { "dose_no": 2, "meal": "lunch", "timing": "after_meal", "offset_min": 30 },
            { "dose_no": 3, "meal": "dinner", "timing": "after_meal", "offset_min": 30 }
          ],
          "cycle": { "type": "daily", "start_date": "2026-11-24" }
        }
      },
      {
        "line_no": 3,
        "raw_text": "무코스타정 1정 3회 3일 식후 30분",
        "drug_id": 1006,
        "drug_name": "무코스타정",
        "dose_per_time": { "text": "1정", "min": 1, "max": 1, "unit": "정", "parsed": true },
        "times_per_day": 3,
        "total_days": 3,
        "instruction_text": "식후 30분",
        "dosage": {
          "parsed_by": "rule",
          "as_needed": false,
          "doses": [
            { "dose_no": 1, "meal": "breakfast", "timing": "after_meal", "offset_min": 30 },
            { "dose_no": 2, "meal": "lunch", "timing": "after_meal", "offset_min": 30 },
            { "dose_no": 3, "meal": "dinner", "timing": "after_meal", "offset_min": 30 }
          ],
          "cycle": { "type": "daily", "start_date": "2026-11-24" }
        }
      }
    ]
  }
  ```
- **기대 동작:** 액상 시럽 단위(`20mL`)와 정제 단위(`1정`) 모두 정확 파싱, `conditions_to_confirm: []`

---

## Case 05 [정상 4] 식전·취침 전 복용 조건 포함 처방
- **예시 이미지:** `./case05.png` (`document_type: "prescription"`)
- **약 목록 요약:**
  1. `란스톤엘에프디티정 30mg` | 1회 용량: `1정` | 1일 횟수: `1회` | 총 일수: `14일` | 복용 조건: `아침 식전 30분`
  2. `모사프리드정 5mg` | 1회 용량: `1정` | 1일 횟수: `3회` | 총 일수: `14일` | 복용 조건: `식전 30분`
  3. `하루날디정 0.2mg` | 1회 용량: `1정` | 1일 횟수: `1회` | 총 일수: `14일` | 복용 조건: `취침 전`
- **정답값 (`POST /scans/{scan_id}/confirm` Request Body & `raw_text` 기준):**
  ```json
  {
    "hospital_name": "구지속편한내과",
    "prescribed_date": "2026-11-24",
    "drugs": [
      {
        "line_no": 1,
        "raw_text": "란스톤엘에프디티정 30mg 1정 1회 14일 아침 식전 30분",
        "drug_id": 1009,
        "drug_name": "란스톤엘에프디티정 30mg",
        "dose_per_time": { "text": "1정", "min": 1, "max": 1, "unit": "정", "parsed": true },
        "times_per_day": 1,
        "total_days": 14,
        "instruction_text": "아침 식전 30분",
        "dosage": {
          "parsed_by": "rule",
          "as_needed": false,
          "doses": [
            { "dose_no": 1, "meal": "breakfast", "timing": "before_meal", "offset_min": 30 }
          ],
          "cycle": { "type": "daily", "start_date": "2026-11-24" }
        }
      },
      {
        "line_no": 2,
        "raw_text": "모사프리드정 5mg 1정 3회 14일 식전 30분",
        "drug_id": 1010,
        "drug_name": "모사프리드정 5mg",
        "dose_per_time": { "text": "1정", "min": 1, "max": 1, "unit": "정", "parsed": true },
        "times_per_day": 3,
        "total_days": 14,
        "instruction_text": "식전 30분",
        "dosage": {
          "parsed_by": "rule",
          "as_needed": false,
          "doses": [
            { "dose_no": 1, "meal": "breakfast", "timing": "before_meal", "offset_min": 30 },
            { "dose_no": 2, "meal": "lunch", "timing": "before_meal", "offset_min": 30 },
            { "dose_no": 3, "meal": "dinner", "timing": "before_meal", "offset_min": 30 }
          ],
          "cycle": { "type": "daily", "start_date": "2026-11-24" }
        }
      },
      {
        "line_no": 3,
        "raw_text": "하루날디정 0.2mg 1정 1회 14일 취침 전",
        "drug_id": 1011,
        "drug_name": "하루날디정 0.2mg",
        "dose_per_time": { "text": "1정", "min": 1, "max": 1, "unit": "정", "parsed": true },
        "times_per_day": 1,
        "total_days": 14,
        "instruction_text": "취침 전",
        "dosage": {
          "parsed_by": "rule",
          "as_needed": false,
          "doses": [
            { "dose_no": 1, "meal": null, "timing": "bedtime", "offset_min": null }
          ],
          "cycle": { "type": "daily", "start_date": "2026-11-24" }
        }
      }
    ]
  }
  ```
- **기대 동작:** `before_meal`(식전 30분) 및 `bedtime`(취침 전, `meal: null`) 조건 정상 매핑, `conditions_to_confirm: []`

---

## Case 06 [정상 5] 필요시(PRN) 복용 약 포함 처방
- **예시 이미지:** `./case06.png` (`document_type: "prescription"`)
- **약 목록 요약:**
  1. `쎄레브렉스캡슐 200mg` | 1회 용량: `1캡슐` | 1일 횟수: `2회` | 총 일수: `7일` | 복용 조건: `아침·저녁 식후 30분`
  2. `타이레놀정 500mg` | 1회 용량: `1정` | 1일 횟수: `null` | 총 일수: `3일` | 복용 조건: `필요시 복용`
- **정답값 (`POST /scans/{scan_id}/confirm` Request Body & `raw_text` 기준):**
  ```json
  {
    "hospital_name": "유가정형외과",
    "prescribed_date": "2026-11-24",
    "drugs": [
      {
        "line_no": 1,
        "raw_text": "쎄레브렉스캡슐 200mg 1캡슐 2회 7일 아침·저녁 식후 30분",
        "drug_id": 1012,
        "drug_name": "쎄레브렉스캡슐 200mg",
        "dose_per_time": { "text": "1캡슐", "min": 1, "max": 1, "unit": "캡슐", "parsed": true },
        "times_per_day": 2,
        "total_days": 7,
        "instruction_text": "아침·저녁 식후 30분",
        "dosage": {
          "parsed_by": "rule",
          "as_needed": false,
          "doses": [
            { "dose_no": 1, "meal": "breakfast", "timing": "after_meal", "offset_min": 30 },
            { "dose_no": 2, "meal": "dinner", "timing": "after_meal", "offset_min": 30 }
          ],
          "cycle": { "type": "daily", "start_date": "2026-11-24" }
        }
      },
      {
        "line_no": 2,
        "raw_text": "타이레놀정 500mg 1정 - 3일 필요시 복용",
        "drug_id": 1013,
        "drug_name": "타이레놀정 500mg",
        "dose_per_time": { "text": "1정", "min": 1, "max": 1, "unit": "정", "parsed": true },
        "times_per_day": null,
        "total_days": 3,
        "instruction_text": "필요시 복용",
        "dosage": {
          "parsed_by": "rule",
          "as_needed": true,
          "doses": [],
          "cycle": { "type": "daily", "start_date": "2026-11-24" }
        }
      }
    ]
  }
  ```
- **기대 동작:** `타이레놀정 500mg`는 `as_needed: true`, `times_per_day: null`, `doses: []`로 저장되며 시간표 및 일일 복용 개수에서 제외(`conditions_to_confirm: []`)

---

## Case 07 [정상 6] 만성질환 다제약물(4종) 복합 처방
- **예시 이미지:** `./case07.png` (`document_type: "prescription"`)
- **약 목록 요약:**
  1. `노바스크정 5mg` | 1회 용량: `1정` | 1일 횟수: `1회` | 총 일수: `30일` | 복용 조건: `아침 식후 30분`
  2. `다이아벡스정 500mg` | 1회 용량: `1정` | 1일 횟수: `2회` | 총 일수: `30일` | 복용 조건: `아침·저녁 식후 즉시`
  3. `크레스토정 10mg` | 1회 용량: `1정` | 1일 횟수: `1회` | 총 일수: `30일` | 복용 조건: `저녁 식후 30분`
  4. `아스피린프로텍트정 100mg` | 1회 용량: `1정` | 1일 횟수: `1회` | 총 일수: `30일` | 복용 조건: `아침 식후 30분`
- **정답값 (`POST /scans/{scan_id}/confirm` Request Body & `raw_text` 기준):**
  ```json
  {
    "hospital_name": "화원대학내과",
    "prescribed_date": "2026-11-24",
    "drugs": [
      {
        "line_no": 1,
        "raw_text": "노바스크정 5mg 1정 1회 30일 아침 식후 30분",
        "drug_id": 1014,
        "drug_name": "노바스크정 5mg",
        "dose_per_time": { "text": "1정", "min": 1, "max": 1, "unit": "정", "parsed": true },
        "times_per_day": 1,
        "total_days": 30,
        "instruction_text": "아침 식후 30분",
        "dosage": {
          "parsed_by": "rule",
          "as_needed": false,
          "doses": [
            { "dose_no": 1, "meal": "breakfast", "timing": "after_meal", "offset_min": 30 }
          ],
          "cycle": { "type": "daily", "start_date": "2026-11-24" }
        }
      },
      {
        "line_no": 2,
        "raw_text": "다이아벡스정 500mg 1정 2회 30일 아침·저녁 식후 즉시",
        "drug_id": 1015,
        "drug_name": "다이아벡스정 500mg",
        "dose_per_time": { "text": "1정", "min": 1, "max": 1, "unit": "정", "parsed": true },
        "times_per_day": 2,
        "total_days": 30,
        "instruction_text": "아침·저녁 식후 즉시",
        "dosage": {
          "parsed_by": "rule",
          "as_needed": false,
          "doses": [
            { "dose_no": 1, "meal": "breakfast", "timing": "after_meal", "offset_min": 0 },
            { "dose_no": 2, "meal": "dinner", "timing": "after_meal", "offset_min": 0 }
          ],
          "cycle": { "type": "daily", "start_date": "2026-11-24" }
        }
      },
      {
        "line_no": 3,
        "raw_text": "크레스토정 10mg 1정 1회 30일 저녁 식후 30분",
        "drug_id": 1016,
        "drug_name": "크레스토정 10mg",
        "dose_per_time": { "text": "1정", "min": 1, "max": 1, "unit": "정", "parsed": true },
        "times_per_day": 1,
        "total_days": 30,
        "instruction_text": "저녁 식후 30분",
        "dosage": {
          "parsed_by": "rule",
          "as_needed": false,
          "doses": [
            { "dose_no": 1, "meal": "dinner", "timing": "after_meal", "offset_min": 30 }
          ],
          "cycle": { "type": "daily", "start_date": "2026-11-24" }
        }
      },
      {
        "line_no": 4,
        "raw_text": "아스피린프로텍트정 100mg 1정 1회 30일 아침 식후 30분",
        "drug_id": 1017,
        "drug_name": "아스피린프로텍트정 100mg",
        "dose_per_time": { "text": "1정", "min": 1, "max": 1, "unit": "정", "parsed": true },
        "times_per_day": 1,
        "total_days": 30,
        "instruction_text": "아침 식후 30분",
        "dosage": {
          "parsed_by": "rule",
          "as_needed": false,
          "doses": [
            { "dose_no": 1, "meal": "breakfast", "timing": "after_meal", "offset_min": 30 }
          ],
          "cycle": { "type": "daily", "start_date": "2026-11-24" }
        }
      }
    ]
  }
  ```
- **기대 동작:** 4종 다제약물 누락 없이 모두 매칭 및 `식후 즉시`(`offset_min: 0`) 정확 반영, `conditions_to_confirm: []`

---

## Case 08 [함정 2 — 없는 약 이름] 공공데이터 미등록 약품 포함
- **예시 이미지:** `./case08.png` (`document_type: "prescription"`)
- **함정 포인트:** 공공데이터(`drugs`) DB에 존재하지 않는 약품명(`다올비타플러스정`)이 포함된 경우
- **`GET /scans/{scan_id}` 단계(수정 전) 기대값:**
  - `drugs[0]` (`다올비타플러스정`): `match.status: "none"`, `match.drug_id: null`
  - `drugs[1]` (`알마겔정`): `match.status: "exact"`
- **확정 정답값 (`POST /scans/{scan_id}/confirm` Request Body & `raw_text` 기준):**
  ```json
  {
    "hospital_name": "다올가정의학과",
    "prescribed_date": "2026-11-24",
    "drugs": [
      {
        "line_no": 1,
        "raw_text": "다올비타플러스정 1정 1회 30일 아침 식후 30분",
        "drug_id": null,
        "drug_name": "다올비타플러스정",
        "dose_per_time": { "text": "1정", "min": 1, "max": 1, "unit": "정", "parsed": true },
        "times_per_day": 1,
        "total_days": 30,
        "instruction_text": "아침 식후 30분",
        "dosage": {
          "parsed_by": "rule",
          "as_needed": false,
          "doses": [
            { "dose_no": 1, "meal": "breakfast", "timing": "after_meal", "offset_min": 30 }
          ],
          "cycle": { "type": "daily", "start_date": "2026-11-24" }
        }
      },
      {
        "line_no": 2,
        "raw_text": "알마겔정 1정 3회 14일 식후 30분",
        "drug_id": 1004,
        "drug_name": "알마겔정",
        "dose_per_time": { "text": "1정", "min": 1, "max": 1, "unit": "정", "parsed": true },
        "times_per_day": 3,
        "total_days": 14,
        "instruction_text": "식후 30분",
        "dosage": {
          "parsed_by": "rule",
          "as_needed": false,
          "doses": [
            { "dose_no": 1, "meal": "breakfast", "timing": "after_meal", "offset_min": 30 },
            { "dose_no": 2, "meal": "lunch", "timing": "after_meal", "offset_min": 30 },
            { "dose_no": 3, "meal": "dinner", "timing": "after_meal", "offset_min": 30 }
          ],
          "cycle": { "type": "daily", "start_date": "2026-11-24" }
        }
      }
    ]
  }
  ```
- **확정 후 기대 동작:** `drug_id: null` 상태로 약 이름 그대로 확정 저장 허용 및 가이드에서 기본 안내 대체 처리

---

## Case 09 [함정 3 — 틀린 용량] 비정상·오인식 용량(`10정`) 포함
- **예시 이미지:** `./case09.png` (`document_type: "prescription"`)
- **함정 포인트:** 처방전 이미지의 `타이레놀8시간이알서방정` 1회 투약량이 `10정`(오타 또는 OCR 오인식)으로 표기된 경우
- **`GET /scans/{scan_id}` 단계(수정 전) 기대값:**
  - `drugs[0]` (`타이레놀8시간이알서방정`): 임의로 고치지 않고 원본 그대로 추출 → `dose_per_time: { "text": "10정", "min": 10, "max": 10, "unit": "정", "parsed": true }`
- **확정 정답값 (`POST /scans/{scan_id}/confirm` Request Body & `raw_text` 기준 — 회원 수정 후 최종 확정본):**
  ```json
  {
    "hospital_name": "현풍중앙의원",
    "prescribed_date": "2026-11-24",
    "drugs": [
      {
        "line_no": 1,
        "raw_text": "타이레놀8시간이알서방정 10정 3회 5일 식후 30분",
        "drug_id": 1018,
        "drug_name": "타이레놀8시간이알서방정",
        "dose_per_time": { "text": "1정", "min": 1, "max": 1, "unit": "정", "parsed": true },
        "times_per_day": 3,
        "total_days": 5,
        "instruction_text": "식후 30분",
        "dosage": {
          "parsed_by": "rule",
          "as_needed": false,
          "doses": [
            { "dose_no": 1, "meal": "breakfast", "timing": "after_meal", "offset_min": 30 },
            { "dose_no": 2, "meal": "lunch", "timing": "after_meal", "offset_min": 30 },
            { "dose_no": 3, "meal": "dinner", "timing": "after_meal", "offset_min": 30 }
          ],
          "cycle": { "type": "daily", "start_date": "2026-11-24" }
        }
      },
      {
        "line_no": 2,
        "raw_text": "스티렌투엑스정 1정 2회 5일 아침·저녁 식후 30분",
        "drug_id": 1019,
        "drug_name": "스티렌투엑스정",
        "dose_per_time": { "text": "1정", "min": 1, "max": 1, "unit": "정", "parsed": true },
        "times_per_day": 2,
        "total_days": 5,
        "instruction_text": "아침·저녁 식후 30분",
        "dosage": {
          "parsed_by": "rule",
          "as_needed": false,
          "doses": [
            { "dose_no": 1, "meal": "breakfast", "timing": "after_meal", "offset_min": 30 },
            { "dose_no": 2, "meal": "dinner", "timing": "after_meal", "offset_min": 30 }
          ],
          "cycle": { "type": "daily", "start_date": "2026-11-24" }
        }
      }
    ]
  }
  ```
- **확정 후 기대 동작:** 확인 화면(B-2)에서 회원이 직접 `1정`으로 수정한 값(`min: 1, max: 1`)으로 최종 확정

---

## Case 10 [함정 4 — 약 하나 빠짐] 마지막 줄 약 누락 주의 처방
- **예시 이미지:** `./case10.png` (`document_type: "prescription"`)
- **함정 포인트:** 총 3개 약물 중 마지막 3번째 줄(`가스모틴정 5mg`)이 흐리게 인쇄되어 OCR·구조화 과정에서 누락되기 쉬운 경우
- **`GET /scans/{scan_id}` 단계(수정 전) 기대값:**
  - 추출 줄 수 `3` (`drugs.length == 3` — 3줄 모두 추출되어야 함, OCR 누락 여부를 보는 케이스)
- **확정 정답값 (`POST /scans/{scan_id}/confirm` Request Body & `raw_text` 기준):**
  ```json
  {
    "hospital_name": "달성연합내과",
    "prescribed_date": "2026-11-24",
    "drugs": [
      {
        "line_no": 1,
        "raw_text": "트라젠타정 5mg 1정 1회 30일 아침 식후 30분",
        "drug_id": 1020,
        "drug_name": "트라젠타정 5mg",
        "dose_per_time": { "text": "1정", "min": 1, "max": 1, "unit": "정", "parsed": true },
        "times_per_day": 1,
        "total_days": 30,
        "instruction_text": "아침 식후 30분",
        "dosage": {
          "parsed_by": "rule",
          "as_needed": false,
          "doses": [
            { "dose_no": 1, "meal": "breakfast", "timing": "after_meal", "offset_min": 30 }
          ],
          "cycle": { "type": "daily", "start_date": "2026-11-24" }
        }
      },
      {
        "line_no": 2,
        "raw_text": "아토르바스타틴정 10mg 1정 1회 30일 저녁 식후 30분",
        "drug_id": 1021,
        "drug_name": "아토르바스타틴정 10mg",
        "dose_per_time": { "text": "1정", "min": 1, "max": 1, "unit": "정", "parsed": true },
        "times_per_day": 1,
        "total_days": 30,
        "instruction_text": "저녁 식후 30분",
        "dosage": {
          "parsed_by": "rule",
          "as_needed": false,
          "doses": [
            { "dose_no": 1, "meal": "dinner", "timing": "after_meal", "offset_min": 30 }
          ],
          "cycle": { "type": "daily", "start_date": "2026-11-24" }
        }
      },
      {
        "line_no": 3,
        "raw_text": "가스모틴정 5mg 1정 3회 30일 식후 30분",
        "drug_id": 1022,
        "drug_name": "가스모틴정 5mg",
        "dose_per_time": { "text": "1정", "min": 1, "max": 1, "unit": "정", "parsed": true },
        "times_per_day": 3,
        "total_days": 30,
        "instruction_text": "식후 30분",
        "dosage": {
          "parsed_by": "rule",
          "as_needed": false,
          "doses": [
            { "dose_no": 1, "meal": "breakfast", "timing": "after_meal", "offset_min": 30 },
            { "dose_no": 2, "meal": "lunch", "timing": "after_meal", "offset_min": 30 },
            { "dose_no": 3, "meal": "dinner", "timing": "after_meal", "offset_min": 30 }
          ],
          "cycle": { "type": "daily", "start_date": "2026-11-24" }
        }
      }
    ]
  }
  ```
- **확정 후 기대 동작:** 3줄 모두 추출되어야 함(OCR 누락 여부를 보는 케이스). 만약 빠지면 B-2에서 회원이 약을 추가하고 그 줄은 `raw_text: null`로 저장

---

## Case 11 [선택 1 — 약봉투] 조제봉투 포맷 인식 (`document_type: "pill_bag"`)
- **예시 이미지:** `./case11.png` (`document_type: "pill_bag"`, API 명세서 6장 기준 약봉투 코드)
- **약 목록 요약:**
  1. `세토펜정 325mg` | 1회 용량: `1정` | 1일 횟수: `3회` | 총 일수: `3일` | 복용 조건: `식후 30분`
  2. `베아제정` | 1회 용량: `1정` | 1일 횟수: `3회` | 총 일수: `3일` | 복용 조건: `식후 30분`
- **정답값 (`POST /scans/{scan_id}/confirm` Request Body & `raw_text` 기준):**
  ```json
  {
    "hospital_name": "다올온누리약국",
    "prescribed_date": "2026-11-24",
    "drugs": [
      {
        "line_no": 1,
        "raw_text": "세토펜정 325mg 1정 3회 3일 식후 30분",
        "drug_id": 1023,
        "drug_name": "세토펜정 325mg",
        "dose_per_time": { "text": "1정", "min": 1, "max": 1, "unit": "정", "parsed": true },
        "times_per_day": 3,
        "total_days": 3,
        "instruction_text": "식후 30분",
        "dosage": {
          "parsed_by": "rule",
          "as_needed": false,
          "doses": [
            { "dose_no": 1, "meal": "breakfast", "timing": "after_meal", "offset_min": 30 },
            { "dose_no": 2, "meal": "lunch", "timing": "after_meal", "offset_min": 30 },
            { "dose_no": 3, "meal": "dinner", "timing": "after_meal", "offset_min": 30 }
          ],
          "cycle": { "type": "daily", "start_date": "2026-11-24" }
        }
      },
      {
        "line_no": 2,
        "raw_text": "베아제정 1정 3회 3일 식후 30분",
        "drug_id": 1024,
        "drug_name": "베아제정",
        "dose_per_time": { "text": "1정", "min": 1, "max": 1, "unit": "정", "parsed": true },
        "times_per_day": 3,
        "total_days": 3,
        "instruction_text": "식후 30분",
        "dosage": {
          "parsed_by": "rule",
          "as_needed": false,
          "doses": [
            { "dose_no": 1, "meal": "breakfast", "timing": "after_meal", "offset_min": 30 },
            { "dose_no": 2, "meal": "lunch", "timing": "after_meal", "offset_min": 30 },
            { "dose_no": 3, "meal": "dinner", "timing": "after_meal", "offset_min": 30 }
          ],
          "cycle": { "type": "daily", "start_date": "2026-11-24" }
        }
      }
    ]
  }
  ```
- **기대 동작:** `document_type: "pill_bag"` 업로드 시 조제약국명 및 약 목록 정상 추출·확정

---

## Case 12 [선택 2 — 개인정보 마스킹] 가상 주민번호·연락처 포함 (`mask_text()` 확인)
- **예시 이미지:** `./case12.png` (`document_type: "prescription"`)
- **테스트 포인트:** 이미지 상단에 가상 환자 성명, 가상 주민등록번호, 가상 연락처(`010-0000-0000`)가 포함된 경우 `mask_text()` 동작 검증
- **`GET /scans/{scan_id}` 단계 기대값:**
  - `masked: true` 반환
  - LLM 구조화 요청 전 `mask_text()`가 이름·주민등록번호·연락처를 마스킹 처리하여 전달하며, 추출된 `drugs[].raw_text` 및 확정 데이터에 개인정보가 남지 않음
- **확정 정답값 (`POST /scans/{scan_id}/confirm` Request Body & `raw_text` 기준):**
  ```json
  {
    "hospital_name": "현풍다올의원",
    "prescribed_date": "2026-11-24",
    "drugs": [
      {
        "line_no": 1,
        "raw_text": "아모잘탄정 5/50mg 1정 1회 30일 아침 식후 30분",
        "drug_id": 1001,
        "drug_name": "아모잘탄정 5/50mg",
        "dose_per_time": { "text": "1정", "min": 1, "max": 1, "unit": "정", "parsed": true },
        "times_per_day": 1,
        "total_days": 30,
        "instruction_text": "아침 식후 30분",
        "dosage": {
          "parsed_by": "rule",
          "as_needed": false,
          "doses": [
            { "dose_no": 1, "meal": "breakfast", "timing": "after_meal", "offset_min": 30 }
          ],
          "cycle": { "type": "daily", "start_date": "2026-11-24" }
        }
      },
      {
        "line_no": 2,
        "raw_text": "무코스타정 1정 3회 30일 식후 30분",
        "drug_id": 1006,
        "drug_name": "무코스타정",
        "dose_per_time": { "text": "1정", "min": 1, "max": 1, "unit": "정", "parsed": true },
        "times_per_day": 3,
        "total_days": 30,
        "instruction_text": "식후 30분",
        "dosage": {
          "parsed_by": "rule",
          "as_needed": false,
          "doses": [
            { "dose_no": 1, "meal": "breakfast", "timing": "after_meal", "offset_min": 30 },
            { "dose_no": 2, "meal": "lunch", "timing": "after_meal", "offset_min": 30 },
            { "dose_no": 3, "meal": "dinner", "timing": "after_meal", "offset_min": 30 }
          ],
          "cycle": { "type": "daily", "start_date": "2026-11-24" }
        }
      }
    ]
  }
  ```

---

## Case 13 [선택 3 — 비경구약 거절] 먹는 약이 아닌 약(`is_oral: false`) 포함
- **예시 이미지:** `./case13.png` (`document_type: "prescription"`)
- **테스트 포인트:** 점안액(`히알유니점안액 0.15%`) 및 외용 연고(`에스로반연고`)처럼 먹는 약이 아닌 약품(`is_oral: false`)만 포함된 처방전
- **약 목록 요약:**
  1. `히알유니점안액 0.15%` | 1회 용량: `1방울` | 1일 횟수: `4회` | 총 일수: `14일` | 용법: `양안 점안` (`is_oral: false`)
  2. `에스로반연고` | 1회 용량: `적당량` | 1일 횟수: `2회` | 총 일수: `7일` | 용법: `환부 도포` (`is_oral: false`)
- **기대 동작 (`GET /scans/{scan_id}` & `POST /scans/{scan_id}/confirm` 기준):**
  - 1차 경구약(먹는 약) 전용 정책에 따라 `is_oral: false` 약물은 등록 대상에서 거절·제외 처리
  - 경구약이 1개도 남지 않으므로 `POST /scans/{scan_id}/confirm` 호출 시 `drugs` 빈 배열 조건 위반으로 `VALIDATION_ERROR` 반환 및 비경구약 제외 안내 노출