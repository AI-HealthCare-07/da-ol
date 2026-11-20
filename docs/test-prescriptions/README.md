# 공용 테스트 처방 시나리오 (1차 3건 / 전체 10건)

> 작성자: 이재경
> 기준 스키마: `daol_API_명세서.md` 6장 `POST /scans/{scan_id}/confirm` Request Body
> 구성: 정상 6건 + 함정 4건 중 1차 우선 제출 3건 (정상 2건 + 함정 1건, 경구약 대상, 비식별 샘플 이미지 포함)

| 번호 | 구분 | 유형 | 이미지 | 약품 수 |
| --- | --- | --- | --- | --- |
| Case 01 | 정상 1 | 고혈압·이상지질혈증 정기 처방 | `./case01.png` | 2개 |
| Case 02 | 정상 2 | 당뇨·위장보호 복합 처방 | `./case02.png` | 2개 |
| Case 03 | 함정 1 | 끼니 안 적힌 1일 2회 | `./case03.png` | 2개 |

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
  - `meal: null`, `timing: null` 상태로 확정 시 `POST /scans/{scan_id}/confirm` 응답의 `conditions_to_confirm` 배열에 `넥시움정 20mg`의 1·2회차(`dose_no: 1, 2`)가 `meal_unknown` / `timing_unknown` 사유로 반환되어 사용자 선택(`PATCH /dose-conditions/{condition_id}`) 유도