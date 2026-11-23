# 공용 테스트 처방 시나리오 (전체 10건 완료)

> 작성자: 이재경
> 기준 스키마: `daol_API_명세서.md` 6장 `POST /scans/{scan_id}/confirm` Request Body
> 구성: 정상 6건 + 함정 4건 (경구약 대상, 개인정보 비식별 샘플 이미지 포함)

| 번호 | 구분 | 유형 | 이미지 | 약품 수 |
| --- | --- | --- | --- | --- |
| Case 01 | 정상 1 | 고혈압·이상지질혈증 정기 처방 | `./case01.png` | 2개 |
| Case 02 | 정상 2 | 당뇨·위장보호 복합 처방 | `./case02.png` | 2개 |
| Case 03 | 함정 1 | 끼니 안 적힌 1일 2회 | `./case03.png` | 2개 |
| Case 04 | 정상 3 | 급성 기관지염·감기 시럽·정제 처방 | `./case04.png` | 3개 |
| Case 05 | 정상 4 | 식전·취침 전 복용 조건 포함 처방 | `./case05.png` | 3개 |
| Case 06 | 정상 5 | 필요시(PRN) 복용 약 포함 처방 | `./case06.png` | 2개 |
| Case 07 | 정상 6 | 만성질환 다제약물(4종) 복합 처방 | `./case07.png` | 4개 |
| Case 08 | 함정 2 | 공공데이터에 없는 약 이름 | `./case08.png` | 2개 |
| Case 09 | 함정 3 | 비정상·오인식 용량 (`10정`) | `./case09.png` | 2개 |
| Case 10 | 함정 4 | 마지막 줄 약 하나 빠짐 주의 처방 | `./case10.png` | 3개 |

---

## Case 01 [정상 1] 고혈압·이상지질혈증 정기 처방
- **예시 이미지:** `./case01.png`
- **약 목록 요약:**
  1. `아모잘탄정 5/50mg` | 1회 용량: `1정` | 1일 횟수: `1회` | 총 일수: `30일` | 복용 조건: `아침 식후 30분`
  2. `리바로정 2mg` | 1회 용량: `1정` | 1일 횟수: `1회` | 총 일수: `30일` | 복용 조건: `저녁 식후 30분`
- **정답값 (`POST /scans/{scan_id}/confirm` Request Body 기준):**
  ```json
  {
    "hospital_name": "다올내과의원",
    "prescribed_date": "2026-11-20",
    "drugs": [
      {
        "line_no": 1,
        "drug_id": 1001,
        "drug_name": "아모잘탄정 5/50mg",
        "dose_per_time": { "text": "1정", "min": 1, "max": 1, "unit": "정", "parsed": true },
        "times_per_day": 1,
        "total_days": 30,
        "instruction_text": "아침 식후 30분",
        "dosage": {
          "parsed_by": "dictionary",
          "as_needed": false,
          "doses": [
            { "dose_no": 1, "meal": "breakfast", "timing": "after_meal", "offset_min": 30 }
          ],
          "cycle": { "type": "daily", "start_date": "2026-11-20" }
        }
      },
      {
        "line_no": 2,
        "drug_id": 1002,
        "drug_name": "리바로정 2mg",
        "dose_per_time": { "text": "1정", "min": 1, "max": 1, "unit": "정", "parsed": true },
        "times_per_day": 1,
        "total_days": 30,
        "instruction_text": "저녁 식후 30분",
        "dosage": {
          "parsed_by": "dictionary",
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
- **예시 이미지:** `./case02.png`
- **약 목록 요약:**
  1. `자누메트정 50/500mg` | 1회 용량: `1정` | 1일 횟수: `2회` | 총 일수: `30일` | 복용 조건: `아침·저녁 식후 30분`
  2. `알마겔정` | 1회 용량: `1정` | 1일 횟수: `3회` | 총 일수: `14일` | 복용 조건: `식후 30분`
- **정답값 (`POST /scans/{scan_id}/confirm` Request Body 기준):**
  ```json
  {
    "hospital_name": "현풍연합내과",
    "prescribed_date": "2026-11-20",
    "drugs": [
      {
        "line_no": 1,
        "drug_id": 1003,
        "drug_name": "자누메트정 50/500mg",
        "dose_per_time": { "text": "1정", "min": 1, "max": 1, "unit": "정", "parsed": true },
        "times_per_day": 2,
        "total_days": 30,
        "instruction_text": "아침·저녁 식후 30분",
        "dosage": {
          "parsed_by": "dictionary",
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
        "drug_id": 1004,
        "drug_name": "알마겔정",
        "dose_per_time": { "text": "1정", "min": 1, "max": 1, "unit": "정", "parsed": true },
        "times_per_day": 3,
        "total_days": 14,
        "instruction_text": "식후 30분",
        "dosage": {
          "parsed_by": "dictionary",
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
- **예시 이미지:** `./case03.png`
- **함정 포인트:** `넥시움정 20mg`의 용법란에 끼니(아침/점심/저녁) 및 식전·식후 조건 없이 `1일 2회 복용`만 기재된 경우
- **약 목록 요약:**
  1. `넥시움정 20mg` | 1회 용량: `1정` | 1일 횟수: `2회` | 총 일수: `14일` | 복용 조건: `1일 2회 복용` (끼니·식전후 미기재)
  2. `무코스타정` | 1회 용량: `1정` | 1일 횟수: `3회` | 총 일수: `14일` | 복용 조건: `식후 30분`
- **정답값 (`POST /scans/{scan_id}/confirm` Request Body 기준):**
  ```json
  {
    "hospital_name": "달성가정의학과",
    "prescribed_date": "2026-11-20",
    "drugs": [
      {
        "line_no": 1,
        "drug_id": 1005,
        "drug_name": "넥시움정 20mg",
        "dose_per_time": { "text": "1정", "min": 1, "max": 1, "unit": "정", "parsed": true },
        "times_per_day": 2,
        "total_days": 14,
        "instruction_text": "1일 2회 복용",
        "dosage": {
          "parsed_by": "dictionary",
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
        "drug_id": 1006,
        "drug_name": "무코스타정",
        "dose_per_time": { "text": "1정", "min": 1, "max": 1, "unit": "정", "parsed": true },
        "times_per_day": 3,
        "total_days": 14,
        "instruction_text": "식후 30분",
        "dosage": {
          "parsed_by": "dictionary",
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
- **기대 동작:**
  - `GET /scans/{scan_id}` 단계에서 `넥시움정 20mg`의 `dosage.needs_confirm: true` 반환
  - `meal: null`, `timing: null` 상태로 확정 시 `POST /scans/{scan_id}/confirm` 응답의 `conditions_to_confirm` 배열에 `넥시움정 20mg`의 1·2회차(`dose_no: 1, 2`)가 `timing_unknown` 사유로 반환되어 사용자 선택(`PATCH /dose-conditions/{condition_id}`) 유도

---

## Case 04 [정상 3] 급성 기관지염·감기 시럽·정제 처방
- **예시 이미지:** `./case04.png`
- **약 목록 요약:**
  1. `코대원포르테시럽` | 1회 용량: `20mL` | 1일 횟수: `3회` | 총 일수: `3일` | 복용 조건: `식후 30분`
  2. `펠루비정` | 1회 용량: `1정` | 1일 횟수: `3회` | 총 일수: `3일` | 복용 조건: `식후 30분`
  3. `무코스타정` | 1회 용량: `1정` | 1일 횟수: `3회` | 총 일수: `3일` | 복용 조건: `식후 30분`
- **정답값 (`POST /scans/{scan_id}/confirm` Request Body 기준):**
  ```json
  {
    "hospital_name": "논공이비인후과",
    "prescribed_date": "2026-11-24",
    "drugs": [
      {
        "line_no": 1,
        "drug_id": 1007,
        "drug_name": "코대원포르테시럽",
        "dose_per_time": { "text": "20mL", "min": 20, "max": 20, "unit": "mL", "parsed": true },
        "times_per_day": 3,
        "total_days": 3,
        "instruction_text": "식후 30분",
        "dosage": {
          "parsed_by": "dictionary",
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
        "drug_id": 1008,
        "drug_name": "펠루비정",
        "dose_per_time": { "text": "1정", "min": 1, "max": 1, "unit": "정", "parsed": true },
        "times_per_day": 3,
        "total_days": 3,
        "instruction_text": "식후 30분",
        "dosage": {
          "parsed_by": "dictionary",
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
        "drug_id": 1006,
        "drug_name": "무코스타정",
        "dose_per_time": { "text": "1정", "min": 1, "max": 1, "unit": "정", "parsed": true },
        "times_per_day": 3,
        "total_days": 3,
        "instruction_text": "식후 30분",
        "dosage": {
          "parsed_by": "dictionary",
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
- **예시 이미지:** `./case05.png`
- **약 목록 요약:**
  1. `란스톤엘에프디티정 30mg` | 1회 용량: `1정` | 1일 횟수: `1회` | 총 일수: `14일` | 복용 조건: `아침 식전 30분`
  2. `모사프리드정 5mg` | 1회 용량: `1정` | 1일 횟수: `3회` | 총 일수: `14일` | 복용 조건: `식전 30분`
  3. `하루날디정 0.2mg` | 1회 용량: `1정` | 1일 횟수: `1회` | 총 일수: `14일` | 복용 조건: `취침 전`
- **정답값 (`POST /scans/{scan_id}/confirm` Request Body 기준):**
  ```json
  {
    "hospital_name": "구지속편한내과",
    "prescribed_date": "2026-11-24",
    "drugs": [
      {
        "line_no": 1,
        "drug_id": 1009,
        "drug_name": "란스톤엘에프디티정 30mg",
        "dose_per_time": { "text": "1정", "min": 1, "max": 1, "unit": "정", "parsed": true },
        "times_per_day": 1,
        "total_days": 14,
        "instruction_text": "아침 식전 30분",
        "dosage": {
          "parsed_by": "dictionary",
          "as_needed": false,
          "doses": [
            { "dose_no": 1, "meal": "breakfast", "timing": "before_meal", "offset_min": 30 }
          ],
          "cycle": { "type": "daily", "start_date": "2026-11-24" }
        }
      },
      {
        "line_no": 2,
        "drug_id": 1010,
        "drug_name": "모사프리드정 5mg",
        "dose_per_time": { "text": "1정", "min": 1, "max": 1, "unit": "정", "parsed": true },
        "times_per_day": 3,
        "total_days": 14,
        "instruction_text": "식전 30분",
        "dosage": {
          "parsed_by": "dictionary",
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
        "drug_id": 1011,
        "drug_name": "하루날디정 0.2mg",
        "dose_per_time": { "text": "1정", "min": 1, "max": 1, "unit": "정", "parsed": true },
        "times_per_day": 1,
        "total_days": 14,
        "instruction_text": "취침 전",
        "dosage": {
          "parsed_by": "dictionary",
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
- **예시 이미지:** `./case06.png`
- **약 목록 요약:**
  1. `쎄레브렉스캡슐 200mg` | 1회 용량: `1캡슐` | 1일 횟수: `2회` | 총 일수: `7일` | 복용 조건: `아침·저녁 식후 30분`
  2. `타이레놀정 500mg` | 1회 용량: `1정` | 1일 횟수: `null` | 총 일수: `3일` | 복용 조건: `필요시 복용`
- **정답값 (`POST /scans/{scan_id}/confirm` Request Body 기준):**
  ```json
  {
    "hospital_name": "유가정형외과",
    "prescribed_date": "2026-11-24",
    "drugs": [
      {
        "line_no": 1,
        "drug_id": 1012,
        "drug_name": "쎄레브렉스캡슐 200mg",
        "dose_per_time": { "text": "1캡슐", "min": 1, "max": 1, "unit": "캡슐", "parsed": true },
        "times_per_day": 2,
        "total_days": 7,
        "instruction_text": "아침·저녁 식후 30분",
        "dosage": {
          "parsed_by": "dictionary",
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
        "drug_id": 1013,
        "drug_name": "타이레놀정 500mg",
        "dose_per_time": { "text": "1정", "min": 1, "max": 1, "unit": "정", "parsed": true },
        "times_per_day": null,
        "total_days": 3,
        "instruction_text": "필요시 복용",
        "dosage": {
          "parsed_by": "dictionary",
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
- **예시 이미지:** `./case07.png`
- **약 목록 요약:**
  1. `노바스크정 5mg` | 1회 용량: `1정` | 1일 횟수: `1회` | 총 일수: `30일` | 복용 조건: `아침 식후 30분`
  2. `다이아벡스정 500mg` | 1회 용량: `1정` | 1일 횟수: `2회` | 총 일수: `30일` | 복용 조건: `아침·저녁 식후 즉시`
  3. `크레스토정 10mg` | 1회 용량: `1정` | 1일 횟수: `1회` | 총 일수: `30일` | 복용 조건: `저녁 식후 30분`
  4. `아스피린프로텍트정 100mg` | 1회 용량: `1정` | 1일 횟수: `1회` | 총 일수: `30일` | 복용 조건: `아침 식후 30분`
- **정답값 (`POST /scans/{scan_id}/confirm` Request Body 기준):**
  ```json
  {
    "hospital_name": "화원대학내과",
    "prescribed_date": "2026-11-24",
    "drugs": [
      {
        "line_no": 1,
        "drug_id": 1014,
        "drug_name": "노바스크정 5mg",
        "dose_per_time": { "text": "1정", "min": 1, "max": 1, "unit": "정", "parsed": true },
        "times_per_day": 1,
        "total_days": 30,
        "instruction_text": "아침 식후 30분",
        "dosage": {
          "parsed_by": "dictionary",
          "as_needed": false,
          "doses": [
            { "dose_no": 1, "meal": "breakfast", "timing": "after_meal", "offset_min": 30 }
          ],
          "cycle": { "type": "daily", "start_date": "2026-11-24" }
        }
      },
      {
        "line_no": 2,
        "drug_id": 1015,
        "drug_name": "다이아벡스정 500mg",
        "dose_per_time": { "text": "1정", "min": 1, "max": 1, "unit": "정", "parsed": true },
        "times_per_day": 2,
        "total_days": 30,
        "instruction_text": "아침·저녁 식후 즉시",
        "dosage": {
          "parsed_by": "dictionary",
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
        "drug_id": 1016,
        "drug_name": "크레스토정 10mg",
        "dose_per_time": { "text": "1정", "min": 1, "max": 1, "unit": "정", "parsed": true },
        "times_per_day": 1,
        "total_days": 30,
        "instruction_text": "저녁 식후 30분",
        "dosage": {
          "parsed_by": "dictionary",
          "as_needed": false,
          "doses": [
            { "dose_no": 1, "meal": "dinner", "timing": "after_meal", "offset_min": 30 }
          ],
          "cycle": { "type": "daily", "start_date": "2026-11-24" }
        }
      },
      {
        "line_no": 4,
        "drug_id": 1017,
        "drug_name": "아스피린프로텍트정 100mg",
        "dose_per_time": { "text": "1정", "min": 1, "max": 1, "unit": "정", "parsed": true },
        "times_per_day": 1,
        "total_days": 30,
        "instruction_text": "아침 식후 30분",
        "dosage": {
          "parsed_by": "dictionary",
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
- **예시 이미지:** `./case08.png`
- **함정 포인트:** 공공데이터(`drugs`) DB에 존재하지 않는 약품명(`다올비타플러스정`)이 포함된 경우
- **약 목록 요약:**
  1. `다올비타플러스정` | 1회 용량: `1정` | 1일 횟수: `1회` | 총 일수: `30일` | 복용 조건: `아침 식후 30분` (DB 미등록)
  2. `알마겔정` | 1회 용량: `1정` | 1일 횟수: `3회` | 총 일수: `14일` | 복용 조건: `식후 30분`
- **정답값 (`POST /scans/{scan_id}/confirm` Request Body 기준):**
  ```json
  {
    "hospital_name": "다올가정의학과",
    "prescribed_date": "2026-11-24",
    "drugs": [
      {
        "line_no": 1,
        "drug_id": null,
        "drug_name": "다올비타플러스정",
        "dose_per_time": { "text": "1정", "min": 1, "max": 1, "unit": "정", "parsed": true },
        "times_per_day": 1,
        "total_days": 30,
        "instruction_text": "아침 식후 30분",
        "dosage": {
          "parsed_by": "dictionary",
          "as_needed": false,
          "doses": [
            { "dose_no": 1, "meal": "breakfast", "timing": "after_meal", "offset_min": 30 }
          ],
          "cycle": { "type": "daily", "start_date": "2026-11-24" }
        }
      },
      {
        "line_no": 2,
        "drug_id": 1004,
        "drug_name": "알마겔정",
        "dose_per_time": { "text": "1정", "min": 1, "max": 1, "unit": "정", "parsed": true },
        "times_per_day": 3,
        "total_days": 14,
        "instruction_text": "식후 30분",
        "dosage": {
          "parsed_by": "dictionary",
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
- **기대 동작:**
  - `GET /scans/{scan_id}` 단계에서 `다올비타플러스정`의 매칭 상태가 `match.status: "none"`, `drug_id: null`로 반환
  - `drug_id: null` 상태로 약 이름 그대로 확정 저장 허용 및 가이드에서 기본 안내 대체 처리

---

## Case 09 [함정 3 — 틀린 용량] 비정상·오인식 용량(`10정`) 포함
- **예시 이미지:** `./case09.png`
- **함정 포인트:** 처방전 이미지의 `타이레놀8시간이알서방정` 1회 투약량이 `10정`(오타 또는 OCR 오인식)으로 표기된 경우
- **약 목록 요약:**
  1. `타이레놀8시간이알서방정` | 이미지 표기 용량: `10정` → 회원 확인 후 수정 용량: `1정` | 1일 횟수: `3회` | 총 일수: `5일` | 복용 조건: `식후 30분`
  2. `스티렌투엑스정` | 1회 용량: `1정` | 1일 횟수: `2회` | 총 일수: `5일` | 복용 조건: `아침·저녁 식후 30분`
- **정답값 (`POST /scans/{scan_id}/confirm` Request Body 기준 — 회원 수정 후 최종 확정본):**
  ```json
  {
    "hospital_name": "현풍중앙의원",
    "prescribed_date": "2026-11-24",
    "drugs": [
      {
        "line_no": 1,
        "drug_id": 1018,
        "drug_name": "타이레놀8시간이알서방정",
        "dose_per_time": { "text": "1정", "min": 1, "max": 1, "unit": "정", "parsed": true },
        "times_per_day": 3,
        "total_days": 5,
        "instruction_text": "식후 30분",
        "dosage": {
          "parsed_by": "dictionary",
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
        "drug_id": 1019,
        "drug_name": "스티렌투엑스정",
        "dose_per_time": { "text": "1정", "min": 1, "max": 1, "unit": "정", "parsed": true },
        "times_per_day": 2,
        "total_days": 5,
        "instruction_text": "아침·저녁 식후 30분",
        "dosage": {
          "parsed_by": "dictionary",
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
- **기대 동작:**
  - `GET /scans/{scan_id}` 단계에서 원본 이미지의 `10정`을 임의로 추측·변경하지 않고 그대로 추출(`text: "10정"`, `min: 10`, `max: 10`)하여 확인 화면(B-2)에서 회원이 직접 `1정`으로 수정하도록 유도

---

## Case 10 [함정 4 — 약 하나 빠짐] 마지막 줄 약 누락 주의 처방
- **예시 이미지:** `./case10.png`
- **함정 포인트:** 총 3개 약물 중 마지막 3번째 줄(`가스모틴정 5mg`)이 흐리게 인쇄되어 OCR·구조화 과정에서 누락되기 쉬운 경우
- **약 목록 요약:**
  1. `트라젠타정 5mg` | 1회 용량: `1정` | 1일 횟수: `1회` | 총 일수: `30일` | 복용 조건: `아침 식후 30분`
  2. `아토르바스타틴정 10mg` | 1회 용량: `1정` | 1일 횟수: `1회` | 총 일수: `30일` | 복용 조건: `저녁 식후 30분`
  3. `가스모틴정 5mg` | 1회 용량: `1정` | 1일 횟수: `3회` | 총 일수: `30일` | 복용 조건: `식후 30분` (흐린 인쇄 줄)
- **정답값 (`POST /scans/{scan_id}/confirm` Request Body 기준):**
  ```json
  {
    "hospital_name": "달성연합내과",
    "prescribed_date": "2026-11-24",
    "drugs": [
      {
        "line_no": 1,
        "drug_id": 1020,
        "drug_name": "트라젠타정 5mg",
        "dose_per_time": { "text": "1정", "min": 1, "max": 1, "unit": "정", "parsed": true },
        "times_per_day": 1,
        "total_days": 30,
        "instruction_text": "아침 식후 30분",
        "dosage": {
          "parsed_by": "dictionary",
          "as_needed": false,
          "doses": [
            { "dose_no": 1, "meal": "breakfast", "timing": "after_meal", "offset_min": 30 }
          ],
          "cycle": { "type": "daily", "start_date": "2026-11-24" }
        }
      },
      {
        "line_no": 2,
        "drug_id": 1021,
        "drug_name": "아토르바스타틴정 10mg",
        "dose_per_time": { "text": "1정", "min": 1, "max": 1, "unit": "정", "parsed": true },
        "times_per_day": 1,
        "total_days": 30,
        "instruction_text": "저녁 식후 30분",
        "dosage": {
          "parsed_by": "dictionary",
          "as_needed": false,
          "doses": [
            { "dose_no": 1, "meal": "dinner", "timing": "after_meal", "offset_min": 30 }
          ],
          "cycle": { "type": "daily", "start_date": "2026-11-24" }
        }
      },
      {
        "line_no": 3,
        "drug_id": 1022,
        "drug_name": "가스모틴정 5mg",
        "dose_per_time": { "text": "1정", "min": 1, "max": 1, "unit": "정", "parsed": true },
        "times_per_day": 3,
        "total_days": 30,
        "instruction_text": "식후 30분",
        "dosage": {
          "parsed_by": "dictionary",
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
- **기대 동작:**
  - 3번째 줄(`가스모틴정 5mg`)이 누락되지 않고 추출되어야 하며, 만약 OCR/구조화 단계에서 빠진 경우 확인 화면(B-2)에서 회원이 `[+ 약 추가하기]`로 보완하여 최종 3개 약물 모두 저장(`VERI-002` 빠진 약 검증 기준 통과)