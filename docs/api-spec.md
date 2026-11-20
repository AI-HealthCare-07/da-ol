# 다올 API 명세서 (1차)

> 기준 문서: 요구사항 정의서 1차 축소안(11/20) · ERD `daol_erd_phase1.dbml` · 와이어프레임(A-1 ~ E-2)
> 자기가 구현할 API는 자기가 작성합니다. 팀장이 프론트 입장에서 전체를 리뷰하고, AI와 백엔드가 맞닿는 부분은 민정님이 리뷰합니다.
> 2·3차 API(화단·통계·상점·알림 등)는 1차가 동작한 뒤에 추가합니다.

| 담당 | 영역 | 섹션 |
| --- | --- | --- |
| 민정 | 공통 규칙 확정, 인증·회원, 처방·복약 | 1, 4 |
| 설아 | 홈·약 정보, 전체 리뷰 | 5 |
| 채민 | OCR, 챗봇 | 6, 7 |
| 유정 | 가이드·검증 | 8 |

---

## 0. 함께 작업하는 방법

1. 각자 `<!-- 담당 START -->` ~ `<!-- 담당 END -->` 사이만 수정합니다. 다른 섹션은 고치지 않고 PR 댓글로 의견을 남깁니다.
2. 섹션 사이의 빈 줄과 구분선(`---`)은 지우지 않습니다. 맞붙은 줄을 두 사람이 고치면 Git 충돌이 납니다.
3. 작업 전에 `git pull origin dev`로 최신 내용을 받고, 브랜치는 `docs/api-이름`(예: `docs/api-seol`)으로 만듭니다.
4. PR 제목은 `docs: API 명세서 ○○ 작성`으로 통일합니다.
5. 다른 영역에 필요한 API가 보이면 직접 쓰지 않고, 담당자에게 말하거나 자기 섹션에 "→ ○○님 확인"이라고 적습니다.
6. 3번 목록의 **상태**도 같이 바꿉니다: `작성 전` → `작성 중` → `리뷰 요청` → `확정`
7. 공통 규칙(1번)을 바꿔야 하면 민정님께 먼저 말씀드리고, 바꾼 내용은 10번 변경 이력에 남깁니다.

---

## 1. 공통 규칙

> 초안입니다. 민정님이 확정합니다.

| 항목 | 규칙 |
| --- | --- |
| 주소 | `/api/v1/...`, 복수형 명사(`/prescriptions`, `/intakes`), 단어 연결은 하이픈(`/health-profile`) |
| 인증 | `Authorization: Bearer {access_token}`. 카카오 로그인·토큰 재발급을 제외한 모든 API에 필요합니다 |
| 권한 | 다른 회원의 데이터에 접근하면 `404`로 응답합니다. 데이터가 있는지 자체를 숨기기 위함입니다(REQ-NFR-003) |
| 형식 | 요청·응답 모두 JSON. 필드 이름은 snake_case이며 ERD 컬럼 이름과 같게 씁니다 |
| 성공 응답 | 데이터를 바로 내려주고 `success`, `data` 등으로 감싸지 않습니다 |
| 날짜·시각 | 한국 시간(KST). 날짜 `2026-11-20`, 시각 `18:30`, 일시 `2026-11-20T18:30:00+09:00` |
| 목록 | `?page=1&size=20` → `{"items": [...], "page": 1, "size": 20, "total": 57}` |
| enum | ERD enum 값을 그대로 씁니다(예: `intake_status` = `pending / taken / missed`) |
| 파일 업로드 | `multipart/form-data`. 파일 1개 10MB, 합계 30MB, jpg·png·pdf |
| 문구 | 진단·처방처럼 읽히는 표현은 쓰지 않습니다. 예시 값도 마찬가지입니다 |

### 1-1. 에러 응답

모든 에러는 아래 형식으로 통일합니다.

```json
{ "code": "NOT_FOUND", "message": "처방을 찾을 수 없어요" }
```

- `code`: 프론트가 분기할 때 쓰는 값입니다(영문 대문자).
- `message`: 화면에 그대로 띄울 수 있는 한국어 문장입니다.

| code | HTTP | 언제 |
| --- | --- | --- |
| `UNAUTHORIZED` | 401 | 토큰이 없거나 만료됨 → 프론트가 재발급을 시도합니다 |
| `PROFILE_REQUIRED` | 403 | 추가 정보 입력 전 회원이 다른 API를 호출함 → 추가 정보 입력 화면으로 보냅니다 |
| `NOT_FOUND` | 404 | 대상이 없거나 다른 회원의 데이터 |
| `VALIDATION_ERROR` | 422 | 입력값 오류. 항목별 사유는 `fields`에 담을 수 있습니다 |
| `RATE_LIMITED` | 429 | 호출 제한 초과(OCR·가이드·챗봇) |
| `EXTERNAL_API_ERROR` | 502 | CLOVA OCR·LLM·공공데이터 호출 실패 |
| `INTERNAL_ERROR` | 500 | 그 외 서버 오류 |

영역별 에러 코드는 각 섹션에서 추가합니다(예: `DOCUMENT_EXPIRED`).

### 1-2. 오래 걸리는 작업 (OCR · 가이드 생성)

1. 요청 API는 작업을 시작하고 바로 `202 Accepted`와 대상 ID를 돌려줍니다.
2. 프론트는 상태 조회 API를 2초 간격으로 호출합니다.
3. 상태 값은 ERD enum(`document_status`, `guide_status`)을 그대로 씁니다.
4. 최대 대기 시간과 실패 시 화면 문구는 각 API 명세에 적습니다.

### 1-3. 챗봇 답변 (스트리밍)

SSE(`text/event-stream`)로 내려주며, 이벤트는 세 가지로 통일합니다.

| event | data 예시 | 설명 |
| --- | --- | --- |
| `delta` | `{"text": "지금 드시는"}` | 답변 글자 조각 |
| `done` | `{"message_id": 812, "message_type": "normal"}` | 답변 끝. `message_type`은 ERD `chat_message_type` 값입니다 |
| `error` | `{"code": "EXTERNAL_API_ERROR", "message": "잠시 후 다시 시도해 주세요"}` | 스트림 도중 실패. 사용 횟수는 차감하지 않습니다 |

### 1-4. 작성 양식

API 하나마다 아래 틀을 복사해서 씁니다.

````markdown
### [METHOD] /api/v1/경로
- 설명:
- 인증: 필요 / 불필요
- 관련 요구사항:
- 관련 화면:
- 관련 테이블:
- Path / Query:
- Request Body:

  ```json
  {}
  ```
- Response Body (200):

  ```json
  {}
  ```
- 에러: `CODE`(HTTP) 언제 → 화면 처리
- 비고:
````

---

## 2. 작성 예시: 복용 체크

> 양식을 어떻게 채우는지 보여드리기 위한 예시입니다. 최종 내용은 민정님이 4번 섹션에서 확정합니다.

### [PATCH] /api/v1/intakes/{intake_id}
- 설명: 복용 기록을 체크하거나 취소합니다. 그날 복용을 모두 마치면 꽃이 핍니다.
- 인증: 필요
- 관련 요구사항: REQ-MED-005, REQ-MED-016, REQ-MED-017
- 관련 화면: A-2 홈(원형 약통 칸, 체크리스트)
- 관련 테이블: `intake_logs`, `daily_flowers`
- Path / Query: Path `intake_id`(`intake_logs.id`)
- Request Body:

  ```json
  { "status": "taken" }
  ```
  `status`는 `taken`(체크) 또는 `pending`(체크 취소)입니다.
- Response Body (200):

  ```json
  {
    "intake_id": 3021,
    "status": "taken",
    "taken_at": "2026-11-20T18:42:10+09:00",
    "day_summary": { "log_date": "2026-11-20", "done_count": 3, "total_count": 3 },
    "flower": { "bloomed": true, "just_bloomed": true }
  }
  ```
- 에러: `NOT_FOUND`(404) 없는 기록·다른 회원의 기록 → 목록 새로고침 / `INTAKE_EDIT_EXPIRED`(422) 최근 3일보다 이전 기록 → "3일이 지난 기록은 수정할 수 없어요"
- 비고:
  - `day_summary`에서 필요시 복용 약은 개수에서 제외합니다.
  - `flower.just_bloomed`가 `true`이면 프론트가 꽃 피는 애니메이션을 보여줍니다.
  - 체크 취소로 하루 완료가 풀리면 `bloomed: false`가 되고 꽃은 삭제됩니다.
  - `intake_logs` 갱신과 `daily_flowers` 생성·삭제는 한 트랜잭션으로 처리합니다.

---

## 3. 1차 API 목록

경로 앞의 `/api/v1`은 생략했습니다. 합계 26개 + 내부 명세 1개입니다(민정님 12 · 채민님 9 · 유정님 3+내부 · 설아님 2).

| 영역 | 메서드 | 경로 | 설명 | 요구사항 | 화면 | 담당 | 상태 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 인증 | POST | `/auth/kakao` | 카카오 인가 코드로 로그인·가입, 토큰 발급 | USER-002 | A-1 | 민정 | 작성 전 |
| 인증 | POST | `/auth/refresh` | 토큰 재발급 | USER-006 | - | 민정 | 작성 전 |
| 인증 | POST | `/auth/logout` | 로그아웃(리프레시 토큰 무효화) | USER-006 | 공통 헤더 | 민정 | 작성 전 |
| 회원 | GET | `/users/me` | 내 정보 | USER-008 | E-1 | 민정 | 작성 전 |
| 회원 | POST | `/users/me/profile` | 추가 정보 입력 + 필수 약관 동의 | USER-002 | A-1 | 민정 | 작성 전 |
| 회원 | GET | `/users/me/health-profile` | 건강 프로필 조회 | USER-010 | E-2 | 민정 | 작성 전 |
| 회원 | PUT | `/users/me/health-profile` | 건강 프로필 저장(기저질환 포함) | USER-010 | E-2 | 민정 | 작성 전 |
| 처방 | GET | `/prescriptions` | 처방 목록(복용 중 / 종료) | MED-002 | C-1 | 민정 | 작성 전 |
| 처방 | GET | `/prescriptions/{prescription_id}` | 처방 상세(약·복용 조건·시간표) | MED-002 | C-1 | 민정 | 작성 전 |
| 처방 | PATCH | `/dose-conditions/{condition_id}` | 복용 조건 확인·선택 | MED-008·009 | B-2 | 민정 | 작성 전 |
| 복약 | GET | `/intakes?date=` | 날짜별 복용 기록(최근 3일) | MED-005 | A-2 | 민정 | 작성 전 |
| 복약 | PATCH | `/intakes/{intake_id}` | 복용 체크·취소 + 꽃 결과 | MED-005·017 | A-2 | 민정 | 작성 중(예시) |
| 홈 | GET | `/home/today` | 원형 약통 화면 데이터 한 번에 | MED-016·017 | A-2 | 설아 | 작성 전 |
| 약 정보 | GET | `/drugs/{drug_id}` | 약 상세(공공데이터) | MED-002 | C-2 | 설아 | 작성 전 |
| OCR | POST | `/documents` | 처방전·약봉투 업로드 → 인식 시작(202) | OCR-001·002 | B-1 | 채민 | 작성 전 |
| OCR | GET | `/documents/{document_id}` | 인식 상태 + 결과 | OCR-003·004 | B-1, B-2 | 채민 | 작성 전 |
| OCR | GET | `/documents/{document_id}/pages/{page_no}/image` | 원본 페이지 이미지 | OCR-004 | B-2 | 채민 | 작성 전 |
| OCR | PATCH | `/documents/{document_id}/items` | 인식 결과 수정 | OCR-004 | B-2 | 채민 | 작성 전 |
| OCR | POST | `/documents/{document_id}/confirm` | 확정 → 처방 생성 | OCR-004 | B-2 | 채민 | 작성 전 |
| OCR | GET | `/drugs/match?name=` | 약품명 매칭 후보(최대 3개) | OCR-005 | B-2 | 채민 | 작성 전 |
| 챗봇 | POST | `/chat/sessions` | 대화방 만들기 | CHAT-001 | F-1 | 채민 | 작성 전 |
| 챗봇 | GET | `/chat/sessions/{session_id}/messages` | 메시지 목록 | CHAT-001 | F-1 | 채민 | 작성 전 |
| 챗봇 | POST | `/chat/sessions/{session_id}/messages` | 질문 보내기(SSE 답변) | CHAT-001·002·004·005 | F-1 | 채민 | 작성 전 |
| 가이드 | POST | `/prescriptions/{prescription_id}/guides` | 가이드 생성 요청(202) | GUIDE-001·002 | D-1, C-1 | 유정 | 작성 전 |
| 가이드 | GET | `/prescriptions/{prescription_id}/guides` | 처방별 가이드 목록·상태 | GUIDE-004 | D-1 | 유정 | 작성 전 |
| 가이드 | GET | `/guides/{guide_id}` | 가이드 내용 + 검증 표시 | GUIDE-001·003·006, VERI-001·004 | D-2 | 유정 | 작성 전 |
| 내부 | - | 가이드 생성 ↔ 검증 데이터 형식 | 외부 API가 아닌 내부 명세 | VERI-001·002·004 | - | 유정 | 작성 전 |

---

<!-- 민정 START · 인증·회원 -->
## 4. 인증·회원 / 처방·복약

담당: 민정 · 관련 화면: A-1, A-2, B-2, C-1, E-1, E-2 · 관련 테이블: `users`, `user_consents`, `refresh_tokens`, `health_profiles`, `user_conditions`, `prescriptions`, `prescription_items`, `dose_conditions`, `dose_schedules`, `intake_logs`, `daily_flowers`

> 1-4 양식을 복사해서 작성합니다.

| 확인할 것 | 같이 볼 사람 |
| --- | --- |
| 첫 로그인 응답에 `is_profile_completed`를 포함합니다. `false`이면 프론트가 추가 정보 입력 화면으로 이동하고, 그 전에는 다른 API가 `PROFILE_REQUIRED`를 돌려줍니다 | 설아 |
| 1차 시간표는 기본 일과(기상 07:00 / 식사 08:00·12:30·18:30 / 취침 23:00)로 계산합니다. 처방 상세 응답에 회차별 시각과 `schedule_status`를 넣습니다 | 설아 |
| 복용 체크는 2번 예시를 이어서 확정합니다 | 설아 |
| OCR 확정이 만드는 처방 데이터 형태 | 채민 |

<!-- 민정 END -->

---

<!-- 설아 START · 홈·약 정보 -->
## 5. 홈·약 정보

담당: 설아 · 관련 화면: A-2, C-2 · 관련 테이블: `intake_logs`, `dose_schedules`, `daily_flowers`, `drugs`

> 1-4 양식을 복사해서 작성합니다.

| 확인할 것 | 같이 볼 사람 |
| --- | --- |
| `/home/today`에 담을 값: 오늘 날짜, 회차 목록(시각·라벨·칸 상태 `done / due / missed`·약 목록), 필요시 약, 요일 미니 약통(7일 완료율), 오늘 꽃 상태, 다음 복용 시각, 기본 일과 사용 여부 | 민정 |
| 약 상세 하단에 데이터 기준일(`drugs.data_fetched_at`)을 표시합니다 | - |

<!-- 설아 END -->

---

<!-- 채민 START · OCR -->
## 6. OCR

담당: 채민 · 관련 화면: B-1, B-2 · 관련 테이블: `medical_documents`, `document_pages`, `drugs`, `prescriptions`(확정 시 생성)

> 1-4 양식을 복사해서 작성합니다.

| 확인할 것 | 같이 볼 사람 |
| --- | --- |
| 확정 API가 만드는 처방 데이터 형태(`prescriptions` · `prescription_items` · `dose_conditions`), 확정 응답에 `prescription_id` 포함 | 민정 |
| 업로드 후 3시간이 지나 만료된 문서는 `DOCUMENT_EXPIRED`로 응답합니다 | 설아 |
| 확인이 필요한 항목(인식 신뢰도가 낮거나 LLM이 해석한 값)은 화면에서 강조해야 하므로, 항목별로 표시 값을 내려줍니다 | 설아 |

<!-- 채민 END -->

---

<!-- 채민 START · 챗봇 -->
## 7. 챗봇

담당: 채민 · 관련 화면: F-1 · 관련 테이블: `chat_sessions`, `chat_messages`

> 1-4 양식을 복사해서 작성합니다.

| 확인할 것 | 같이 볼 사람 |
| --- | --- |
| SSE 이벤트는 1-3 공통 형식을 따릅니다 | 설아 |
| 응급 키워드면 `done.message_type`이 `emergency_physical` / `emergency_self_harm`, 범위 밖 질문이면 `out_of_scope`입니다. 프론트는 이 값으로 119·109 안내를 먼저 보여줍니다 | 설아 |
| LLM에는 최근 10턴만 보내고, 복용 중인 약과 건강 프로필을 함께 넘깁니다(CHAT-002) | 민정 |

<!-- 채민 END -->

---

<!-- 유정 START · 가이드·검증 -->
## 8. 가이드·검증

담당: 유정 · 관련 화면: D-1, D-2, C-1(가이드 보기) · 관련 테이블: `guides`, `prompt_versions`, `rag_documents`

> 1-4 양식을 복사해서 작성합니다.

| 확인할 것 | 같이 볼 사람 |
| --- | --- |
| 상태 값은 `guide_status`(`generating / verifying / completed / completed_with_replacements`)를 씁니다. 화면 문구와 1:1로 맞춥니다 | 설아 |
| 가이드 내용 JSON 안에 항목별 `check_status`와 근거(`drug_id` 또는 `rag_document_id`)를 넣어 '출처 확인됨 / 확인 필요'를 표시합니다 | 설아 |
| 1차는 검증에 실패한 항목을 기본 약 정보로 대체합니다(재생성은 2차) | 민정 |
| 가이드 생성과 검증 사이에 주고받는 데이터 형식(내부 명세)도 이 섹션에 정리합니다 | 민정 |

<!-- 유정 END -->

---

## 9. 팀 확인 요청

| No | 내용 | 확인할 사람 |
| --- | --- | --- |
| 1 | 공통 규칙(1번) 확정: 에러 코드 목록, 상태 조회 간격(2초), 토큰 만료 시간 | 민정 |
| 2 | 동의 없음·추가 정보 미입력을 403으로 둘지 다른 코드로 둘지 | 민정 |
| 3 | 개발 중에는 FastAPI Swagger(`/docs`)와 이 문서를 대조하고, 기능이 끝나면 문서를 최신 상태로 맞춥니다 | 전원 |

---

## 10. 변경 이력

| 날짜 | 작성자 | 내용 |
| --- | --- | --- |
| 2026-11-20 | 설아 | 초안 작성: 공통 규칙, 작성 양식, 예시, 1차 API 목록, 담당 배정 |
