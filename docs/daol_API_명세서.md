# 다올 API 명세서 (1차)

> 기준 문서: 요구사항 정의서 1차 축소안(11/20) · ERD `daol_erd_phase1.dbml` · 와이어프레임(A-1 ~ F-1) · AI 파트 기획 문서 v5(AI A 채민님 / AI B 유정님)
> 자기가 구현할 API는 자기가 작성합니다. 팀장이 프론트 입장에서 전체를 리뷰하고, AI와 백엔드가 맞닿는 부분은 민정님이 리뷰합니다.
> 2·3차 API(화단·통계·상점·알림 등)는 1차가 동작한 뒤에 추가합니다.

| 담당 | 영역 | 섹션 |
| --- | --- | --- |
| 민정 | 공통 규칙 확정, 인증·회원·건강 프로필, 복용 기록 / 공통 테이블, 백엔드 배포 | 1, 4 |
| 설아 | 홈·약 정보·처방 조회, 전체 리뷰 / 프론트 배포 | 5 |
| 채민 | 처방 등록(OCR·구조화·약품 매칭), 복용 조건 확인, 가이드 검증(내부) | 6 |
| 유정 | 가이드·RAG, 챗봇 / 공공데이터 `drugs` 적재 | 7 |

API가 아닌 작업 분담은 3-1에 정리했습니다.

---

## 0. 함께 작업하는 방법

1. 각자 `<!-- 담당 START -->` ~ `<!-- 담당 END -->` 사이만 수정합니다. 다른 섹션은 고치지 않고 PR 댓글로 의견을 남깁니다.
2. 섹션 사이의 빈 줄과 구분선(`---`)은 지우지 않습니다. 맞붙은 줄을 두 사람이 고치면 Git 충돌이 납니다.
3. 작업 전에 `git pull origin dev`로 최신 내용을 받고, 브랜치는 `docs/api-이름`(예: `docs/api-seol`)으로 만듭니다.
4. PR 제목은 `docs: API 명세서 ○○ 작성`으로 통일합니다.
5. 다른 영역에 필요한 API가 보이면 직접 쓰지 않고, 담당자에게 말하거나 자기 섹션에 "→ ○○님 확인"이라고 적습니다.
6. 3번 목록의 **상태**도 같이 바꿉니다: `작성 전` → `작성 중` → `리뷰 요청` → `확정`
7. 공통 규칙(1번)을 바꿔야 하면 민정님께 먼저 말씀드리고, 바꾼 내용은 9번 변경 이력에 남깁니다.

---

## 1. 공통 규칙

> 11/20 민정님이 확정했습니다. 바꿀 때는 0번 7항을 따릅니다.

| 항목 | 규칙 |
| --- | --- |
| 주소 | `/api/v1/...`, 복수형 명사(`/prescriptions`, `/intakes`), 단어 연결은 하이픈(`/health-profile`) |
| 인증 | `Authorization: Bearer {access_token}`. 카카오 로그인·토큰 재발급을 제외한 모든 API에 필요합니다. 액세스 토큰 30분, 리프레시 토큰 14일 |
| 권한 | 다른 회원의 데이터에 접근하면 `403`이 아닌 `404`로 응답합니다. 데이터가 있는지 자체를 숨기기 위함입니다(REQ-NFR-003, 요구사항 정의서도 `404`로 수정) |
| 형식 | 요청·응답 모두 JSON. 필드 이름은 snake_case이며 ERD 컬럼 이름과 같게 씁니다. 단, Path와 응답의 기본키는 `id` 대신 `{대상}_id`로 씁니다(예: `intake_id`, `prescription_id`) |
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
| `PROFILE_REQUIRED` | 403 | 추가 정보 입력 또는 필수 약관 동의 전 회원이 다른 API를 호출함 → 추가 정보 입력 화면으로 보냅니다. 예외 API: `/auth/*`, `GET /users/me`, `POST /users/me/profile` |
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

SSE(`text/event-stream`)로 내려줍니다. 이벤트 순서는 AI 파트 기획 문서 6-3을 따릅니다. 1차에 쓰는 이벤트만 적었습니다.

| 순서 | event | 언제 | data |
| --- | --- | --- | --- |
| 1 | `emergency` | 응급 표현이 있을 때, AI 답변보다 먼저 | `{"type": "119" 또는 "109", "message": "..."}`. 109면 바로 `done`으로 끝납니다 |
| 1' | `out_of_scope` | 답할 수 없는 질문일 때 | `{"type": "diagnosis" / "prescription_change" / "unrelated", "message": "..."}` → 바로 `done` |
| 2 | `token` | 답변 글자 조각(여러 번) | `{"text": "지금 드시는"}` |
| 3 | `sources` | 답변이 끝났을 때 | 근거 문서 이름 목록 |
| 4 | `done` | 마지막 | `{"message_id": 812}` |
| - | `error` | 도중에 실패 | `{"code": "EXTERNAL_API_ERROR", "message": "답변을 불러오지 못했어요. 다시 보내기를 눌러 주세요"}`. 사용 횟수는 차감하지 않습니다 |

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

경로 앞의 `/api/v1`은 생략했습니다. AI 파트가 먼저 정리한 API는 AI 파트 기획 문서 6장의 이름을 그대로 가져왔습니다. 합계 27개 + 내부 함수 4개입니다(민정 10+내부 1 · 채민 7+내부 1 · 유정 6+내부 1 · 설아 4+내부 1).

| 영역 | 메서드 | 경로 | 설명 | 요구사항 | 화면 | 담당 | 상태 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 인증 | POST | `/auth/kakao` | 카카오 인가 코드로 로그인·가입, 토큰 발급 | USER-002 | A-1 | 민정 | 작성 전 |
| 인증 | POST | `/auth/refresh` | 토큰 재발급 | USER-006 | - | 민정 | 작성 전 |
| 인증 | POST | `/auth/logout` | 로그아웃(리프레시 토큰 무효화) | USER-006 | 공통 헤더 | 민정 | 작성 전 |
| 회원 | GET | `/users/me` | 내 정보 | USER-008 | E-1 | 민정 | 작성 전 |
| 회원 | POST | `/users/me/profile` | 추가 정보 입력 + 필수 약관 동의 | USER-002 | A-1 | 민정 | 작성 전 |
| 회원 | GET | `/users/me/health-profile` | 건강 프로필 조회 | USER-010 | E-2 | 민정 | 작성 전 |
| 회원 | PUT | `/users/me/health-profile` | 건강 프로필 저장(기저질환 포함) | USER-010 | E-2 | 민정 | 작성 전 |
| 복약 | GET | `/intakes?date=` | 날짜별 복용 기록(최근 3일) | MED-005 | A-2 | 민정 | 작성 전 |
| 복약 | PATCH | `/intakes/{intake_id}` | 복용 체크·취소 + 꽃 결과 | MED-005·017 | A-2 | 민정 | 작성 중(예시) |
| 처방 | POST | `/prescriptions` | 처방 직접 입력(약 검색 + 숫자 입력 + 복용 조건 선택) → `create_prescription()` | MED-001 | B-1(직접 입력) | 민정 | 작성 전 |
| 홈 | GET | `/home/today` | 원형 약통 화면 데이터 한 번에 | MED-016·017 | A-2 | 설아 | 작성 전 |
| 약 정보 | GET | `/drugs/{drug_id}` | 약 상세(공공데이터) | MED-002 | C-2 | 설아 | 작성 전 |
| 처방 | GET | `/prescriptions` | 처방 목록(복용 중 / 종료) | MED-002 | C-1 | 설아 | 작성 전 |
| 처방 | GET | `/prescriptions/{prescription_id}` | 처방 상세(약·복용 조건·시간표) | MED-002 | C-1 | 설아 | 작성 전 |
| 처방 등록 | POST | `/scans` | 처방전·약봉투 파일 업로드 → 읽기 시작(202) | OCR-001·002 | B-1 | 채민 | 리뷰 요청 |
| 처방 등록 | GET | `/scans/{scan_id}` | 진행 상태 또는 인식 결과 | OCR-002·003·004 | B-1, B-2 | 채민 | 리뷰 요청 |
| 처방 등록 | PATCH | `/scans/{scan_id}` | 인식 결과 수정·문서 종류 다시 고르기 | OCR-001·004 | B-2 | 채민 | 리뷰 요청 |
| 처방 등록 | GET | `/scans/{scan_id}/pages/{page_no}/image` | 원본 페이지 이미지 | OCR-004 | B-2 | 채민 | 리뷰 요청 |
| 처방 등록 | POST | `/scans/{scan_id}/confirm` | 확정 → `create_prescription()` 호출 → 원본 삭제 | OCR-004 | B-2 | 채민 | 리뷰 요청 |
| 약 정보 | GET | `/drugs?q=&limit=` | 약 검색(OCR 매칭 후보는 `limit=3`, 직접 입력 검색은 기본 10) | OCR-005, MED-001 | B-2, B-1(직접 입력) | 채민 | 리뷰 요청 |
| 처방 등록 | PATCH | `/dose-conditions/{condition_id}` | '복용 조건 확인 필요' 항목을 회원이 고름 | MED-008 | B-2 | 채민 | 리뷰 요청 |
| 가이드 | GET | `/prescriptions/{prescription_id}/guides` | 복약·생활습관 가이드 보기(만드는 중이면 진행 상태) | GUIDE-001·002·004·006·007 | D-2, C-1 | 유정 | 작성 전 |
| 가이드 | POST | `/prescriptions/{prescription_id}/guides/retry` | 실패 화면의 [다시 시도] | GUIDE-007 | D-2 | 유정 | 작성 전 |
| 가이드 | GET | `/guides` | 내 가이드 목록 | GUIDE-004 | D-1 | 유정 | 작성 전 |
| 챗봇 | GET | `/chat/suggestions` | 추천 질문 3개 | CHAT-001 | F-1 | 유정 | 작성 전 |
| 챗봇 | POST | `/chat/sessions` | 채팅창을 열 때 새 대화 만들기 | CHAT-001 | F-1 | 유정 | 작성 전 |
| 챗봇 | POST | `/chat/sessions/{session_id}/messages` | 질문 보내기 → 답변(SSE) | CHAT-001·002·004·005, VERI-004 | F-1 | 유정 | 작성 전 |
| 내부 | - | `verify_guide()` | 가이드 검증(원문 대조·빠진 약·금지 표현) | VERI-001·002·004 | - | 채민 | 작성 전 |
| 내부 | - | `start_guide_generation()` | 처방 확정 후 가이드 생성 시작(비동기) | GUIDE-001·002 | - | 유정 | 작성 전 |
| 내부 | - | `get_confirmed_prescription()` | 확정 처방 + 회차별 복용 조건 조회 | OCR-004, MED-008 | - | 설아 | 작성 전 |
| 내부 | - | `create_prescription()` | 처방 저장 → 시간표 계산 → 복용 기록 생성 → 가이드 생성 시작(OCR 확정·직접 입력 공용) | OCR-004, MED-001·009 | - | 민정 | 작성 전 |

---

### 3-1. API가 아닌 작업 분담

API 개수만으로는 보이지 않는 작업을 함께 나눕니다.

| 작업 | 담당 | 내용 |
| --- | --- | --- |
| 공통 규칙·인증 미들웨어 | 민정 | 1번 공통 규칙 확정, JWT 인증·`PROFILE_REQUIRED` 처리 |
| 공통 테이블 | 민정 | `users`, `prescriptions`, `prescription_items`, `dose_conditions`처럼 여러 사람이 쓰는 테이블의 모델·마이그레이션을 먼저 올립니다. 나머지 테이블은 각자 자기 API가 쓰는 테이블을 만듭니다 |
| 처방 저장 함수 | 민정 | `create_prescription()` 하나로 처방·약·복용 조건 저장, 기본 일과로 `dose_schedules` 계산, `intake_logs` 생성, `start_guide_generation()` 호출까지 한 번에 처리합니다. OCR 확정과 직접 입력이 모두 이 함수를 부르므로 저장 로직이 두 벌로 갈라지지 않습니다 |
| 공공데이터 `drugs` 적재 | 유정 | RAG용 e약은요 데이터를 받을 때 `drugs` 테이블에도 함께 넣습니다. 같은 데이터를 두 번 받지 않도록 한 파이프라인으로 처리합니다 |
| 백엔드 배포 | 민정 | EC2 + Docker Compose (NFR-007) |
| 프론트 배포 | 설아 | 프론트는 백엔드와 따로 배포합니다(Vercel 등). 백엔드 주소 연결 방식은 민정님과 맞춥니다 |

---

<!-- 민정 START · 인증·회원 -->
## 4. 인증·회원 / 복용 기록 / 처방 직접 입력

담당: 민정 · 관련 화면: A-1, A-2, B-1(직접 입력), E-1, E-2 · 관련 테이블: `users`, `user_consents`, `refresh_tokens`, `health_profiles`, `user_conditions`, `intake_logs`, `daily_flowers`, `prescriptions`, `prescription_items`, `dose_conditions`, `dose_schedules` · 내부 함수: `create_prescription()`

> 1-4 양식을 복사해서 작성합니다.

| 확인할 것 | 같이 볼 사람 |
| --- | --- |
| 첫 로그인 응답에 `is_profile_completed`를 포함합니다. `false`이면 프론트가 추가 정보 입력 화면으로 이동하고, 그 전에는 다른 API가 `PROFILE_REQUIRED`를 돌려줍니다 | 설아 |
| 건강 프로필 항목은 가이드·챗봇 개인화 입력이라, 필드 이름을 정할 때 유정님과 맞춥니다 | 유정 |
| 복용 체크는 2번 예시를 이어서 확정합니다 | 설아 |
| 처방 확정 시 복용 기록(`intake_logs`)을 언제부터 만들지(등록 시각 이후 회차부터) | 채민 |
| `drugs` 테이블 컬럼은 ERD 기준으로 먼저 정해 두고, 적재는 유정님이 맡습니다 | 유정 |
| 직접 입력(MED-001) 1차 범위: 약은 `GET /drugs?q=`로 검색해서 고르고, 1회 용량·1일 횟수·총 일수·복용 시작일은 숫자로 입력, 복용 조건은 식전 n분 / 식후 n분 / 취침 전 / 필요시 중에서 고릅니다. 식간·공복·n시간 간격과 문장 해석(`POST /dosage/parse`)은 2차입니다 | 설아 · 채민 |
| `create_prescription()` 입력 형식은 OCR 확정 결과와 직접 입력이 같은 형식을 쓰도록 채민님과 맞춥니다 | 채민 |

<!-- 민정 END -->

---

<!-- 설아 START · 홈·약 정보 -->
## 5. 홈·약 정보·처방 조회

담당: 설아 · 관련 화면: A-2, C-1, C-2 · 관련 테이블: `intake_logs`, `dose_schedules`, `daily_flowers`, `drugs`, `prescriptions`, `prescription_items`, `dose_conditions` · 내부 함수: `get_confirmed_prescription()`

> 1-4 양식을 복사해서 작성합니다.

| 확인할 것 | 같이 볼 사람 |
| --- | --- |
| `/home/today`에 담을 값: 오늘 날짜, 회차 목록(시각·라벨·칸 상태 `done / due / missed`·약 목록), 필요시 약, 요일 미니 약통(7일 완료율), 오늘 꽃 상태, 다음 복용 시각, 기본 일과 사용 여부 | 민정 |
| 약 상세 하단에 데이터 기준일(`drugs.data_fetched_at`)을 표시합니다 | - |
| 처방 등록 화면(B-1)에 '직접 입력하기' 진입을 추가합니다. OCR이 실패했을 때도 이 화면으로 안내합니다 | 민정 |
| 1차 시간표는 기본 일과(기상 07:00 / 식사 08:00·12:30·18:30 / 취침 23:00)로 계산합니다. 1일 1·2회인데 끼니가 없으면 '복용 시간 확인 필요'로 둡니다. 처방 상세 응답에 회차별 시각과 `schedule_status`를 넣습니다 | 민정 |
| 처방 상세 조회(`GET /prescriptions/{prescription_id}`)와 `get_confirmed_prescription()`은 같은 조회 함수 하나로 만듭니다. 화면과 가이드·검증이 같은 처방 데이터를 쓰게 하기 위함입니다 | 채민 · 유정 |
| `get_confirmed_prescription()` 반환 형식: 약마다 `prescription_drug_id`, 약품명, 1회 용량(`{text, min, max, unit, parsed}`), 1일 횟수, 총 일수, 회차별 복용 조건, 복용 시각을 담습니다. AI 파트 기획 문서 4-3 확정본·4-9 형식을 따릅니다 | 채민 · 유정 |
| 복용 시각은 민정님이 계산한 `dose_schedules` 값을 읽기만 합니다 | 민정 |

<!-- 설아 END -->

---

<!-- 채민 START · 처방 등록·검증 -->
## 6. 처방 등록·검증 (AI A)

담당: 채민 · 관련 화면: B-1, B-2 · 관련 테이블: `medical_documents`, `document_pages`, `drugs`, `prescriptions`·`prescription_items`·`dose_conditions`(확정 시 생성)

> AI 파트 기획 문서 v5의 6-1(AI A), 4-3, 4-10, 11-2를 1-4 양식으로 옮겨 적습니다.

> 퇴원요약지(OCR-006·007)는 범위에서 빠졌으므로 문서 종류는 `prescription`(처방전) / `pill_bag`(약봉투) 두 가지만 받습니다. AI 문서 4-3의 `diagnoses[]`·`discharge_notes[]`·`excluded_drugs[]`와 페이지 순서 바꾸기는 넣지 않았습니다.
> AI 문서 4-3에서 바꾼 점: `scan_id`는 숫자(`medical_documents.id`), 약품 매칭은 `drug_code` 대신 `drug_id`(`drugs.id`)를 씁니다(1번 공통 규칙). 감량 단계(`taper_steps`)·간격(`interval_hours`)·약 형태(`form`)는 1차 직접 입력 범위에 맞춰 뺐습니다.

| 확인할 것 | 같이 볼 사람 |
| --- | --- |
| ✅ 확정 API는 채민님이 맡고, 저장은 민정님의 `create_prescription()`을 부릅니다(AI 문서 D11, 11/20). 채민님은 인식 결과를 이 함수의 입력 형식으로 넘기고 원본을 삭제합니다 | 민정 · 유정 |
| `create_prescription()` 입력 형식을 `POST /scans/{scan_id}/confirm` Request Body와 같게 제안했습니다. 직접 입력(`POST /prescriptions`)도 같은 모양(`source`만 다름)을 쓰면 됩니다 → 민정님 확인 | 민정 |
| 약 검색은 `GET /drugs?q=&limit=` 하나로 처리합니다. 자동완성이라 1번의 목록 규칙(`page`·`size`·`total`) 대신 `{"items": [...]}`만 돌려주는 예외로 적었습니다 → 민정님 확인(공통 규칙 예외) | 민정 · 설아 |
| 진행 상태 값: 1-2 규칙대로 ERD `document_status`(`uploaded / ocr_done / ocr_failed / confirmed / expired`)를 그대로 쓰고, 로딩 문구용으로 `step`(`reading / structuring`)을 따로 둡니다(6-1). AI 문서 4-10 값은 쓰지 않습니다 → 민정·설아님 확인 | 민정 · 설아 |
| 칸별 신뢰도 `{value, confidence, needs_check}`로 확인 화면의 노란색 강조를 표시합니다(6-2) | 설아 |
| 원본 이미지 API는 인증 헤더가 필요해서 `<img src>`로 바로 쓸 수 없습니다. `fetch`로 받아 blob URL로 띄워 주세요 | 설아 |
| 업로드 장 수 상한(제안 10장)과 OCR 호출 제한(제안 회원당 하루 20회) 값을 정해야 합니다(AI 문서 D22) | 민정 |
| 복용 기록 생성 시점(4번 질문에 대한 답): 확정 시각 이후 회차부터 만드는 것을 제안합니다. 복용 시작일이 과거여도 지난 회차는 만들지 않고, 종료일(시작일 + 총 일수)은 그대로 둡니다 | 민정 |
| `dose_conditions` 한 행 = 약 한 줄의 회차 하나로 가정했습니다. 다르면 `PATCH /dose-conditions` 모양을 바꿉니다. 조건을 바꾼 뒤 시간표·복용 기록을 다시 계산할 함수가 필요합니다 | 민정 |
| 1차 시간표가 계산하지 않는 조건(식간·공복·n시간 간격, 매일이 아닌 주기)은 인식은 하되 `needs_confirm: true`로 보내고, 확정 때는 1차 허용 값만 받습니다(6-2) | 민정 · 설아 |
| 공공데이터에 없는 약(`drug_id: null`)도 이름 그대로 저장할 수 있게 했습니다. 이 약의 가이드는 "이 약은 안내 정보가 없어요"로 나갑니다 | 민정 · 유정 |
| `verify_guide()` 입력·출력은 AI 문서 4-1·4-2 형식을 따릅니다. 마지막 시도에서 실패한 항목에 `fallback`을 표시하는 것까지 검증 함수가 하고, 기본 정보로 바꿔 끼우는 일은 가이드 생성 쪽에서 하는 안입니다 | 유정 |
| 확정 후 복용 조건을 바꾸면 가이드의 `dose_times`가 시간표와 달라집니다. 가이드 조회 때 시간표 값으로 덮어 보여 주는 안을 제안합니다 | 유정 |

### 6-1. 진행 상태 (`document_status` + `step`)

| `status` | `step` | 화면 | 다음 행동 |
| --- | --- | --- | --- |
| `uploaded` | `reading` | "처방전을 읽고 있어요" | 2초마다 다시 조회 |
| `uploaded` | `structuring` | "약 정보를 정리하고 있어요" | 2초마다 다시 조회 |
| `ocr_done` | `null` | 인식 결과 확인 화면(B-2) | 회원이 확인·수정 후 확정 |
| `ocr_failed` | `null` | `message` + [다시 찍기] / [직접 입력하기] | B-1으로 돌아가거나 직접 입력(`POST /prescriptions`) |
| `confirmed` | `null` | 처방 상세로 이동 | `prescription_id` 사용 |
| `expired` | `null` | "올린 지 3시간이 지나 파일이 삭제됐어요. 다시 올려 주세요" | B-1 |

- `ocr_done`은 OCR과 약 정보 정리가 **모두** 끝난 상태입니다(이름은 ERD를 따름).
- 최대 대기 시간: 업로드 후 **90초**(제안, 가상 처방전 테스트 후 조정). 90초가 지나도 끝나지 않으면 서버가 `ocr_failed`(`fail_reason: timeout`)로 바꾸고, 프론트도 90초가 지나면 조회를 멈추고 실패 화면을 보여 줍니다.

실패 사유(`fail_reason`)와 화면 문구(`message`)는 아래와 같습니다. `message`는 서버가 내려 주므로 그대로 띄우면 됩니다.

| `fail_reason` | 언제 | `message` |
| --- | --- | --- |
| `ocr_error` | CLOVA OCR 오류·10초 초과가 재시도 2회 후에도 계속됨 | "인식에 실패했어요. 잠시 후 다시 올리거나 직접 입력해 주세요" |
| `no_text` | 글자를 거의 읽지 못함(흐림·빛 반사·잘림) | "글자를 읽지 못했어요. 밝은 곳에서 문서 전체가 나오게 다시 찍어 주세요" |
| `no_drug_found` | 글자는 읽었지만 약 줄을 찾지 못함 | "약 정보를 찾지 못했어요. 문서 종류를 다시 고르거나 직접 입력해 주세요" |
| `structure_error` | 약 정보 정리가 1회 재요청 후에도 실패 | "약 정보를 정리하지 못했어요. 직접 입력해 주세요" |
| `timeout` | 90초 안에 끝나지 않음 | "인식에 실패했어요. 잠시 후 다시 올리거나 직접 입력해 주세요" |

### 6-2. 인식 결과에서 쓰는 모양

**칸 객체**: OCR에서 읽은 칸은 `{value, confidence, needs_check}`로 내려줍니다. `needs_check`가 `true`인 칸만 노란색 + "확인이 필요해요"로 표시합니다.

| 칸 | `confidence` | `needs_check`가 `true`인 경우 |
| --- | --- | --- |
| OCR 글자에서 바로 온 칸(약품명, 숫자) | 그 칸을 이루는 OCR 단어 신뢰도 중 가장 낮은 값 | 0.8 미만(출발점, 테스트 후 조정) |
| 정리하면서 원문과 다른 형태로 바뀐 칸 | `null` | 항상 |
| 회원이 고친 칸 | `null` | 항상 `false` |

**용량**(`dose_per_time`): AI 문서 4-9 모양 `{text, min, max, unit, parsed}`에 `confidence`, `needs_check`를 더합니다. `parsed: false`(적당량 등)면 `needs_check: true`이고 "용량을 확인해 주세요"를 띄웁니다. 용량은 필수 칸이 아니라 그대로 확정할 수 있습니다.

**약품 매칭**(`match`):

| `status` | 뜻 | 화면 |
| --- | --- | --- |
| `exact` | 약품 DB와 정확히 일치. `drug_id`가 채워짐 | 확인 불필요 |
| `candidates` | 비슷한 약 최대 3개(`candidates[]`) | 후보 3개 중 고르기 + [다른 약 검색] |
| `none` | 비슷한 약 없음 | "등록되지 않은 약품이에요" + [약 검색] (`GET /drugs`) |

**복용 조건**(`dosage`): AI 문서 4-3-1을 1차 범위로 줄였습니다.

| 칸 | 값 |
| --- | --- |
| `parsed_by` | `dictionary`(표현 사전) / `llm` / `user`(회원이 고름) |
| `needs_confirm` | `llm`이거나 해석 실패, 또는 1차에서 계산하지 않는 조건이면 `true` → "복용 조건을 확인해 주세요" |
| `as_needed` | 필요시 복용이면 `true`. 시간표·알림에서 빠집니다(MED-008) |
| `doses[]` | 회차마다 `{dose_no, meal, timing, offset_min}` |
| └ `meal` | `breakfast` / `lunch` / `dinner` / `null`(끼니 모름) |
| └ `timing` | 1차 허용 값: `after_meal` / `before_meal` / `bedtime` / `null`(아직 못 정함). 인식 단계에서는 `between_meals`·`empty_stomach`·`interval`도 나올 수 있지만, 이때는 `needs_confirm: true`이고 확정 때는 허용 값으로 골라야 합니다 |
| └ `offset_min` | 식전·식후 몇 분. 원문에 없으면 `null` |
| `cycle` | `{type, start_date}`. `type`은 1차에 `daily`만 시간표를 계산합니다(`every_other_day`·`weekly`는 인식되면 `needs_confirm: true`) → 민정님 확인. `start_date`는 처방일을 읽었으면 처방일, 아니면 오늘 |

### 6-3. 처방 등록 에러 코드

1-1 공통 코드에 더해 이 영역에서만 쓰는 코드입니다.

| code | HTTP | 언제 | `message` |
| --- | --- | --- | --- |
| `FILE_TOO_LARGE` | 413 | 파일 1개 10MB 또는 합계 30MB 초과 | "파일 용량이 너무 커요. 한 개에 10MB, 모두 합쳐 30MB까지 올릴 수 있어요" |
| `UNSUPPORTED_FILE_TYPE` | 415 | jpg·png·pdf가 아님(확장자가 아니라 파일 내용으로 판단) | "jpg, png, pdf 파일만 올릴 수 있어요" |
| `ENCRYPTED_PDF` | 422 | 암호가 걸린 PDF | "암호가 걸린 PDF는 읽을 수 없어요. 암호를 푼 파일이나 사진으로 올려 주세요" |
| `INVALID_FILE` | 422 | 손상되었거나 열 수 없는 파일 | "파일을 열 수 없어요. 다른 파일로 다시 올려 주세요" |
| `TOO_MANY_PAGES` | 422 | 페이지 합계가 상한 초과(제안 10장) | "한 번에 10장까지 올릴 수 있어요" |
| `DOCUMENT_NOT_READY` | 409 | 아직 읽는 중이거나 읽기에 실패한 문서를 수정·확정하려 함 | "아직 처방전을 읽고 있어요" |
| `DOCUMENT_ALREADY_CONFIRMED` | 409 | 이미 확정한 문서 | "이미 등록된 처방이에요" |
| `DOCUMENT_EXPIRED` | 410 | 업로드 후 3시간이 지나 원본이 삭제됨 | "올린 지 3시간이 지나 파일이 삭제됐어요. 다시 올려 주세요" |

### [POST] /api/v1/scans
- 설명: 처방전·약봉투 파일을 올리고 글자 읽기를 시작합니다. 한 번에 올린 파일 묶음이 처방 한 건입니다. 읽기는 비동기로 진행되므로 바로 `202`를 돌려주고, 프론트는 `GET /scans/{scan_id}`로 진행 상태를 조회합니다(1-2).
- 인증: 필요
- 관련 요구사항: REQ-OCR-001, REQ-OCR-002, REQ-NFR-004
- 관련 화면: B-1 처방 등록(사진 올리기·촬영 가이드·로딩)
- 관련 테이블: `medical_documents`, `document_pages`
- Path / Query: 없음
- Request Body (`multipart/form-data`):

  | 칸 | 필수 | 설명 |
  | --- | --- | --- |
  | `files` | O | 파일 여러 개. jpg·png·pdf, 1개 10MB·합계 30MB. 올린 순서대로 페이지 번호를 매깁니다 |
  | `document_type` | O | `prescription`(처방전) / `pill_bag`(약봉투) |

  ```
  files: 처방전_앞.jpg, 처방전_뒤.jpg
  document_type: prescription
  ```
- Response Body (202):

  ```json
  {
    "scan_id": 42,
    "status": "uploaded",
    "step": "reading",
    "document_type": "prescription",
    "page_count": 2,
    "expires_at": "2026-11-20T21:30:00+09:00"
  }
  ```
- 에러: `VALIDATION_ERROR`(422) 파일 없음·`document_type` 누락이나 잘못된 값 → 해당 칸 표시 / `FILE_TOO_LARGE`(413)·`UNSUPPORTED_FILE_TYPE`(415)·`ENCRYPTED_PDF`(422)·`INVALID_FILE`(422)·`TOO_MANY_PAGES`(422) → 올리는 단계에서 `message` 표시 후 다시 고르기 / `RATE_LIMITED`(429) OCR 호출 제한 초과 → "오늘은 더 이상 올릴 수 없어요. 직접 입력해 주세요" / `EXTERNAL_API_ERROR`는 여기서 돌려주지 않습니다(읽기 실패는 상태 조회의 `ocr_failed`로 알림)
- 비고:
  - 파일 크기·형식·암호·손상 검사는 요청을 받을 때 끝내고, 통과한 경우에만 `202`를 돌려줍니다.
  - PDF는 페이지마다 이미지로 바꿔 `document_pages`에 저장합니다. PDF 페이지는 그 파일 자리에 펼쳐서 번호를 매깁니다(예: 사진 1장 + 3쪽 PDF → 1, 2, 3, 4).
  - 이미지·PDF 모두 페이지별로 CLOVA OCR을 부릅니다(1차는 전자 PDF도 OCR). 페이지마다 10초가 넘거나 오류가 나면 최대 2회 다시 부릅니다.
  - 약 정보 정리(LLM)에 넘기기 전에 주민등록번호·환자번호·이름·면허번호·연락처를 가립니다. OCR 글자는 로그·AI 호출 기록에 남기지 않습니다(NFR-004).
  - `expires_at`은 업로드 시각 + 3시간입니다. 그때까지 확정하지 않으면 정리 작업이 원본 파일·페이지 이미지·인식 결과를 지우고 `expired`로 바꿉니다. 수정해도 연장되지 않습니다.

### [GET] /api/v1/scans/{scan_id}
- 설명: 진행 상태를 돌려줍니다. 인식이 끝났으면(`ocr_done`) 확인 화면(B-2)에 쓸 인식 결과를 함께 돌려줍니다.
- 인증: 필요
- 관련 요구사항: REQ-OCR-002, REQ-OCR-003, REQ-OCR-004, REQ-OCR-005, REQ-MED-008
- 관련 화면: B-1 로딩, B-2 인식 결과 확인
- 관련 테이블: `medical_documents`, `document_pages`
- Path / Query: Path `scan_id`(`medical_documents.id`)
- Request Body: 없음
- Response Body (200):

  읽는 중(`uploaded`)

  ```json
  {
    "scan_id": 42,
    "status": "uploaded",
    "step": "structuring",
    "document_type": "prescription",
    "expires_at": "2026-11-20T21:30:00+09:00"
  }
  ```

  인식 완료(`ocr_done`)

  ```json
  {
    "scan_id": 42,
    "status": "ocr_done",
    "step": null,
    "document_type": "prescription",
    "expires_at": "2026-11-20T21:30:00+09:00",
    "pages": [{ "page_no": 1 }, { "page_no": 2 }],
    "masked": true,
    "prompt_version": "structure_v1",
    "edited": false,
    "hospital_name": { "value": "가상내과의원", "confidence": 0.97, "needs_check": false },
    "prescribed_date": { "value": "2026-11-20", "confidence": 0.93, "needs_check": false },
    "drugs": [
      {
        "line_no": 1,
        "page_no": 1,
        "raw_text": "가상정5mg 1 3 5 식후30분",
        "drug_name": { "value": "가상정5mg", "confidence": 0.91, "needs_check": false },
        "match": { "status": "exact", "drug_id": 1203, "candidates": [] },
        "dose_per_time": { "text": "1정", "min": 1, "max": 1, "unit": "정", "parsed": true, "confidence": 0.95, "needs_check": false },
        "times_per_day": { "value": 3, "confidence": 0.72, "needs_check": true },
        "total_days": { "value": 5, "confidence": 0.94, "needs_check": false },
        "instruction_text": "식후30분",
        "dosage": {
          "parsed_by": "dictionary",
          "needs_confirm": false,
          "as_needed": false,
          "doses": [
            { "dose_no": 1, "meal": "breakfast", "timing": "after_meal", "offset_min": 30 },
            { "dose_no": 2, "meal": "lunch", "timing": "after_meal", "offset_min": 30 },
            { "dose_no": 3, "meal": "dinner", "timing": "after_meal", "offset_min": 30 }
          ],
          "cycle": { "type": "daily", "start_date": "2026-11-20" }
        }
      },
      {
        "line_no": 2,
        "page_no": 1,
        "raw_text": "가상캡슐 1 2 5",
        "drug_name": { "value": "가상캡슐", "confidence": 0.84, "needs_check": false },
        "match": {
          "status": "candidates",
          "drug_id": null,
          "candidates": [
            { "drug_id": 2210, "drug_name": "가상캡슐 250mg", "company_name": "가상제약", "similarity": 0.81 },
            { "drug_id": 2211, "drug_name": "가상캡슐 500mg", "company_name": "가상제약", "similarity": 0.79 }
          ]
        },
        "dose_per_time": { "text": "1캡슐", "min": 1, "max": 1, "unit": "캡슐", "parsed": true, "confidence": 0.9, "needs_check": false },
        "times_per_day": { "value": 2, "confidence": 0.88, "needs_check": false },
        "total_days": { "value": 5, "confidence": 0.9, "needs_check": false },
        "instruction_text": null,
        "dosage": {
          "parsed_by": "dictionary",
          "needs_confirm": true,
          "as_needed": false,
          "doses": [
            { "dose_no": 1, "meal": null, "timing": null, "offset_min": null },
            { "dose_no": 2, "meal": null, "timing": null, "offset_min": null }
          ],
          "cycle": { "type": "daily", "start_date": "2026-11-20" }
        }
      }
    ]
  }
  ```

  실패(`ocr_failed`)

  ```json
  {
    "scan_id": 42,
    "status": "ocr_failed",
    "step": null,
    "document_type": "prescription",
    "fail_reason": "no_text",
    "message": "글자를 읽지 못했어요. 밝은 곳에서 문서 전체가 나오게 다시 찍어 주세요"
  }
  ```

  확정됨(`confirmed`) / 만료(`expired`)

  ```json
  { "scan_id": 42, "status": "confirmed", "step": null, "prescription_id": 88 }
  ```
  ```json
  { "scan_id": 42, "status": "expired", "step": null }
  ```
- 에러: `NOT_FOUND`(404) 없는 문서·다른 회원의 문서 → "처방전을 찾을 수 없어요" 후 B-1로 이동
- 비고:
  - 상태별 화면과 최대 대기 시간은 6-1, 칸 모양과 노란색 표시 규칙은 6-2를 따릅니다.
  - `drugs[]`는 원문 줄 순서(`line_no`)대로 내려주고, 같은 약이 여러 줄이어도 합치지 않습니다. `page_no`는 그 줄이 나온 페이지로, 확인 화면에서 원본 페이지를 나란히 보여 줄 때 씁니다.
  - `PATCH`로 고친 값이 있으면 고친 값이 반영된 결과를 내려주고 `edited: true`가 됩니다.
  - 원본 이미지는 이 응답에 넣지 않고 `GET /scans/{scan_id}/pages/{page_no}/image`로 받습니다.

### [PATCH] /api/v1/scans/{scan_id}
- 설명: 확인 화면에서 고친 값을 저장하거나, 문서 종류를 다시 골라 약 정보를 다시 정리합니다. 문서 종류를 바꿔도 OCR은 다시 하지 않습니다.
- 인증: 필요
- 관련 요구사항: REQ-OCR-001, REQ-OCR-004, REQ-OCR-005, REQ-MED-008
- 관련 화면: B-2 인식 결과 확인
- 관련 테이블: `medical_documents`
- Path / Query: Path `scan_id`(`medical_documents.id`)
- Request Body: 아래 두 가지 중 하나만 보냅니다. 둘을 함께 보내면 `VALIDATION_ERROR`입니다.

  ① 고친 값 저장 → `200`. 바꾼 칸만 보냅니다. 약 줄은 `line_no`로 가리키고, 새 줄은 `line_no` 없이, 지울 줄은 `"deleted": true`로 보냅니다.

  ```json
  {
    "prescribed_date": "2026-11-19",
    "drugs": [
      { "line_no": 1, "times_per_day": 3 },
      { "line_no": 2, "drug_id": 2210 },
      { "line_no": 2, "dosage": { "as_needed": false, "doses": [
        { "dose_no": 1, "meal": "breakfast", "timing": "after_meal", "offset_min": 30 },
        { "dose_no": 2, "meal": "dinner", "timing": "after_meal", "offset_min": 30 }
      ] } },
      { "line_no": 3, "deleted": true },
      { "drug_name": "가상시럽", "drug_id": null, "dose_per_time": { "text": "5mL" }, "times_per_day": 3, "total_days": 3 }
    ]
  }
  ```

  ② 문서 종류 다시 고르기 → `202`

  ```json
  { "document_type": "pill_bag" }
  ```
- Response Body (200 / 202):

  ① 200: `GET /scans/{scan_id}`의 `ocr_done` 응답과 같은 모양(`edited: true`)

  ② 202:

  ```json
  { "scan_id": 42, "status": "uploaded", "step": "structuring", "document_type": "pill_bag" }
  ```
- 에러: `NOT_FOUND`(404) 없는 문서·다른 회원의 문서 / `VALIDATION_ERROR`(422) 없는 `line_no`·없는 `drug_id`·1차에서 받지 않는 `timing` → `fields`의 칸 표시 / `DOCUMENT_NOT_READY`(409) 아직 읽는 중 → 로딩 화면 유지 / `DOCUMENT_ALREADY_CONFIRMED`(409) → 처방 상세로 이동 / `DOCUMENT_EXPIRED`(410) → B-1로 이동
- 비고:
  - 고친 칸은 `confidence: null`, `needs_check: false`가 됩니다. `dosage`를 고르면 `parsed_by: "user"`, `needs_confirm: false`가 됩니다.
  - 용량을 글자로 고치면(`{"text": "5mL"}`) 서버가 표현 사전으로 `min`·`max`·`unit`·`parsed`를 다시 채웁니다.
  - 문서 종류를 다시 고르면 그동안 고친 값은 지우고 처음부터 다시 정리합니다. 확인 화면에서 "고친 내용이 사라져요"를 먼저 물어 주세요.
  - 문서 종류 다시 고르기는 `ocr_done`과 `ocr_failed`(`fail_reason`이 `no_drug_found`·`structure_error`일 때)에서만 받습니다.
  - 꼭 이 API로 저장하지 않고 확정 API에 최종 값을 한 번에 보내도 됩니다. 이 API는 새로고침·뒤로 가기에 대비한 중간 저장용입니다.

### [GET] /api/v1/scans/{scan_id}/pages/{page_no}/image
- 설명: 확인 화면에서 인식 결과와 나란히 보여 줄 원본 페이지 이미지를 돌려줍니다. PDF는 페이지 이미지로 바꾼 것을 돌려줍니다.
- 인증: 필요
- 관련 요구사항: REQ-OCR-004
- 관련 화면: B-2 인식 결과 확인(원본 보기)
- 관련 테이블: `document_pages`
- Path / Query: Path `scan_id`(`medical_documents.id`), `page_no`(1부터)
- Request Body: 없음
- Response Body (200): JSON이 아닌 이미지 파일입니다. `Content-Type: image/jpeg`
- 에러: `NOT_FOUND`(404) 없는 문서·없는 페이지·다른 회원의 문서 → 원본 칸에 "이미지를 불러올 수 없어요" / `DOCUMENT_NOT_READY`(409) 페이지 이미지를 아직 만드는 중 / `DOCUMENT_EXPIRED`(410) 만료되었거나 확정 후 삭제됨 → B-1로 이동
- 비고:
  - `Authorization` 헤더가 필요해서 `<img src="...">`로 바로 쓸 수 없습니다. `fetch`로 받아 `URL.createObjectURL()`로 띄워 주세요.
  - `Cache-Control: no-store`로 내려서 브라우저에 남지 않게 합니다. 확정하면 원본이 지워지므로 확정 뒤에는 이 API를 부르지 않습니다.
  - 회원 본인의 문서라 화면에는 가리지 않은 원본을 보여 줍니다. 가리기(NFR-004)는 LLM에 넘기는 글자와 로그에 적용합니다.

### [POST] /api/v1/scans/{scan_id}/confirm
- 설명: 회원이 확인한 값으로 처방을 확정합니다. 필수 칸을 검사한 뒤 `create_prescription()`으로 처방·약·복용 조건을 저장하고(시간표 계산, 복용 기록 생성, 가이드 생성 시작 포함), 원본 파일을 지웁니다.
- 인증: 필요
- 관련 요구사항: REQ-OCR-004, REQ-OCR-005, REQ-MED-008, REQ-MED-009, REQ-NFR-004
- 관련 화면: B-2 인식 결과 확인([저장하기])
- 관련 테이블: `medical_documents`, `document_pages`, `prescriptions`·`prescription_items`·`dose_conditions`·`dose_schedules`·`intake_logs`(`create_prescription()`이 생성)
- Path / Query: Path `scan_id`(`medical_documents.id`)
- Request Body: 화면에 보이는 최종 값을 모두 보냅니다(칸 객체가 아니라 값만). 이 모양이 `create_prescription()` 입력이 됩니다.

  ```json
  {
    "hospital_name": "가상내과의원",
    "prescribed_date": "2026-11-20",
    "drugs": [
      {
        "line_no": 1,
        "drug_id": 1203,
        "drug_name": "가상정 5mg",
        "dose_per_time": { "text": "1정", "min": 1, "max": 1, "unit": "정", "parsed": true },
        "times_per_day": 3,
        "total_days": 5,
        "instruction_text": "식후30분",
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
      },
      {
        "line_no": 2,
        "drug_id": 2210,
        "drug_name": "가상캡슐 250mg",
        "dose_per_time": { "text": "1캡슐", "min": 1, "max": 1, "unit": "캡슐", "parsed": true },
        "times_per_day": 2,
        "total_days": 5,
        "instruction_text": null,
        "dosage": {
          "parsed_by": "dictionary",
          "as_needed": false,
          "doses": [
            { "dose_no": 1, "meal": null, "timing": null, "offset_min": null },
            { "dose_no": 2, "meal": null, "timing": null, "offset_min": null }
          ],
          "cycle": { "type": "daily", "start_date": "2026-11-20" }
        }
      }
    ]
  }
  ```

  | 필수 칸 | 규칙 |
  | --- | --- |
  | `drugs` | 1개 이상 |
  | `drugs[].drug_name` | 빈칸 불가. 공공데이터에 없는 약은 `drug_id: null`로 이름만 저장 가능 |
  | `drugs[].dose_per_time.text` | 빈칸 불가(`parsed: false`도 저장 가능) |
  | `drugs[].times_per_day` | 1 이상의 정수. `as_needed: true`면 `null` 가능 |
  | `drugs[].total_days` | 1 이상의 정수 |
  | `drugs[].dosage.cycle.type`, `start_date` | 1차는 `daily`만 |
  | `drugs[].dosage.doses[].timing` | `after_meal` / `before_meal` / `bedtime` / `null`. `null`이거나 식전·식후인데 `meal`이 `null`이면 '복용 조건 확인 필요'로 저장됩니다 |
- Response Body (201):

  ```json
  {
    "scan_id": 42,
    "status": "confirmed",
    "prescription_id": 88,
    "conditions_to_confirm": [
      { "condition_id": 5014, "prescription_item_id": 502, "drug_name": "가상캡슐 250mg", "dose_no": 1, "reason": "meal_unknown" },
      { "condition_id": 5015, "prescription_item_id": 502, "drug_name": "가상캡슐 250mg", "dose_no": 2, "reason": "meal_unknown" }
    ]
  }
  ```
  `reason`: `meal_unknown`(끼니를 모름) / `timing_unknown`(식전·식후·취침 전을 모름)
- 에러: `VALIDATION_ERROR`(422) 필수 칸 빈칸·잘못된 값 → [저장하기]를 막고 `fields`의 칸을 표시 / `NOT_FOUND`(404) 없는 문서·다른 회원의 문서 / `DOCUMENT_NOT_READY`(409) 아직 읽는 중·읽기 실패 / `DOCUMENT_ALREADY_CONFIRMED`(409) 이미 확정 → `GET /scans/{scan_id}`의 `prescription_id`로 처방 상세 이동 / `DOCUMENT_EXPIRED`(410) → "올린 지 3시간이 지나 파일이 삭제됐어요. 다시 올려 주세요"

  ```json
  {
    "code": "VALIDATION_ERROR",
    "message": "빈칸을 채워 주세요",
    "fields": { "drugs[1].total_days": "총 일수를 입력해 주세요" }
  }
  ```
- 비고:
  - 처리 순서: ① 필수 칸 검사 → ② `create_prescription(source="ocr", medical_document_id=42, ...)` 호출(민정님 함수, 한 트랜잭션) → ③ 문서 상태 `confirmed`, `prescription_id` 저장 → ④ 원본 파일·페이지 이미지·OCR 글자·인식 결과 삭제.
  - ④ 삭제에 실패해도 응답은 성공으로 돌려주고, 정리 작업이 다시 지웁니다. ②가 실패하면 상태는 `ocr_done`으로 남고 원본도 지우지 않으므로 회원이 다시 [저장하기]를 누를 수 있습니다.
  - 같은 요청이 두 번 들어와도 처방이 두 번 생기지 않도록 문서 행을 잠그고 상태를 확인합니다.
  - `conditions_to_confirm`이 비어 있지 않으면 B-2에서 이어서 복용 조건을 고르게 하고(`PATCH /dose-conditions/{condition_id}`), 비어 있으면 처방 상세로 이동합니다. 1일 3회처럼 끼니를 기본값으로 정할 수 있는 경우는 민정님 시간표 규칙을 따르므로 이 목록에 들어가지 않습니다.
  - 복용 기록은 확정 시각 이후 회차부터 만드는 것을 제안합니다(위 '확인할 것' 표).
  - `drug_id: null`인 약은 가이드에서 "이 약은 안내 정보가 없어요"로 나갑니다(VERI-003 1차 범위).

### [GET] /api/v1/drugs
- 설명: 약품명(상품명·성분명)으로 약을 검색합니다. 확인 화면의 약품 매칭 후보(`limit=3`)와 직접 입력의 약 검색(기본 10개)이 같이 씁니다.
- 인증: 필요
- 관련 요구사항: REQ-OCR-005, REQ-MED-001
- 관련 화면: B-2 인식 결과 확인([약 검색]), B-1 직접 입력(약 검색)
- 관련 테이블: `drugs`
- Path / Query: Query `q`(필수, 공백을 뺀 1~50자), `limit`(선택, 기본 10, 1~20)
- Request Body: 없음
- Response Body (200):

  ```json
  {
    "items": [
      { "drug_id": 1203, "drug_name": "가상정 5mg", "ingredient_name": "가상성분", "company_name": "가상제약", "has_public_data": true, "matched_by": "exact", "similarity": 1.0 },
      { "drug_id": 1204, "drug_name": "가상정 10mg", "ingredient_name": "가상성분", "company_name": "가상제약", "has_public_data": true, "matched_by": "prefix", "similarity": 0.86 }
    ]
  }
  ```
- 에러: `VALIDATION_ERROR`(422) `q`가 비었거나 50자 초과, `limit` 범위 밖 → 프론트에서 먼저 막음
- 비고:
  - 자동완성이라 1번 목록 규칙(`page`·`size`·`total`)을 쓰지 않습니다(공통 규칙 예외, 민정님 확인).
  - 검색 전에 공백·괄호를 지우고 비교합니다(예: "가상정 5mg"와 "가상정5mg"는 같음).
  - 정렬: 정확 일치(`exact`) → 앞부분 일치(`prefix`) → 이름 유사도(`similar`, pg_trgm) 순입니다. 유사도 기준은 0.3에서 시작해 가상 처방전 테스트 후 조정합니다.
  - 결과가 없으면 `{"items": []}`를 돌려줍니다. 화면에는 "검색 결과가 없어요. 약 이름 그대로 저장할 수도 있어요"를 띄웁니다.
  - OCR 약품 매칭은 HTTP를 거치지 않고 같은 검색 함수를 서버 안에서 부릅니다. 정확 일치가 1개면 `exact`, 아니면 기준 이상 상위 3개를 `candidates`, 없으면 `none`입니다.
  - 응답 칸 이름(`drug_name`, `ingredient_name`, `company_name`)은 ERD `drugs` 컬럼이 정해지면 맞춥니다 → 민정·유정님 확인. 약 상세는 설아님의 `GET /drugs/{drug_id}`를 씁니다.
  - 입력할 때마다 부르지 않도록 프론트에서 300ms 디바운스를 부탁드립니다.

### [PATCH] /api/v1/dose-conditions/{condition_id}
- 설명: 처방 확정 뒤에도 '복용 조건 확인 필요'로 남은 회차의 복용 조건을 회원이 목록에서 골라 저장합니다. 저장하면 그 회차의 복용 시각과 앞으로의 복용 기록을 다시 계산합니다.
- 인증: 필요
- 관련 요구사항: REQ-MED-008
- 관련 화면: B-2 인식 결과 확인(확정 직후 이어서 고르기), C-1 처방 상세의 '확인 필요' 표시에서 진입 → 설아님 확인
- 관련 테이블: `dose_conditions`, `dose_schedules`, `intake_logs`
- Path / Query: Path `condition_id`(`dose_conditions.id`, 약 한 줄의 회차 하나)
- Request Body:

  ```json
  { "meal": "breakfast", "timing": "after_meal", "offset_min": 30 }
  ```

  | 칸 | 규칙 |
  | --- | --- |
  | `timing` | `after_meal`(식후 n분) / `before_meal`(식전 n분) / `bedtime`(취침 전) |
  | `meal` | 식전·식후면 `breakfast` / `lunch` / `dinner` 필수, 취침 전이면 `null` |
  | `offset_min` | 식전·식후면 0~120 필수, 취침 전이면 `null` |
- Response Body (200):

  ```json
  {
    "condition_id": 5014,
    "prescription_item_id": 502,
    "dose_no": 1,
    "meal": "breakfast",
    "timing": "after_meal",
    "offset_min": 30,
    "parsed_by": "user",
    "needs_confirm": false,
    "dose_time": "08:30",
    "remaining_to_confirm": 1
  }
  ```
  `remaining_to_confirm`은 같은 처방에서 아직 확인이 필요한 회차 수입니다. `0`이 되면 처방 상세로 이동합니다.
- 에러: `NOT_FOUND`(404) 없는 조건·다른 회원의 조건 / `VALIDATION_ERROR`(422) 위 규칙 위반 → 해당 칸 표시
- 비고:
  - 1차에 고를 수 있는 조건은 직접 입력(MED-001)과 같습니다. 식간·공복·n시간 간격은 2차입니다.
  - '필요시'는 약 단위 조건이라 이 API로 바꾸지 않습니다. 1차에는 확정 전에 B-2에서 고릅니다.
  - 이미 확인이 끝난 조건도 다시 고칠 수 있습니다.
  - 저장 후 시간표·복용 기록 재계산은 민정님 함수(예: `recalculate_schedule(prescription_item_id)`)를 부릅니다. 오늘 이후의 `pending` 기록만 바꾸고 `taken` 기록은 그대로 둡니다 → 민정님 확인.
  - `dose_time`은 그 함수가 계산한 값을 그대로 돌려줍니다. 가이드의 `dose_times`와 달라질 수 있어 유정님과 맞춥니다('확인할 것' 표).

### [내부] verify_guide()
- 설명: AI B가 만든 가이드(생성본 1개)를 확정 처방·시간표와 규칙으로 대조해 통과 여부와 실패 사유를 돌려줍니다. LLM을 부르지 않습니다. 재시도 횟수는 세지 않고, 몇 번째 생성본인지만 기록합니다(AI 문서 C4).
- 인증: 해당 없음(서버 안에서 호출)
- 관련 요구사항: REQ-VERI-001, REQ-VERI-002, REQ-VERI-003(1차 최소 범위), REQ-VERI-004, REQ-VERI-005
- 관련 화면: D-2 가이드 보기('확인 필요' 표시)
- 관련 테이블: `drugs`(공공데이터 여부 조회). 검증 결과 저장(`guide_attempts`)은 2차이며, 1차는 서버 로그에만 남깁니다
- 호출하는 곳: AI B 가이드 생성(`start_guide_generation()` 안, 가이드를 만든 직후)
- 입력:

  ```python
  def verify_guide(
      guide: dict,                       # AI 문서 4-1 가이드 JSON (생성본 1개)
      prescription: dict,                # get_confirmed_prescription() 반환값 (복용 시각 포함)
      *,
      guide_id: int,
      attempt_no: int,                   
      is_last_attempt: bool = False,     # 1차는 attempt_no=1, is_last_attempt=True로만 호출. 여러 번 시도·15초 한도(803줄)는 2차
      user_conditions: list[str] | None = None,           # 기저질환 (VERI-004 ⓒ 진단 단정 검사)
      retrieved_doc_ids: dict[int, list[str]] | None = None,  # prescription_item_id → 이번 검색 doc_id (2차 VERI-003)
  ) -> dict: ...                         # AI 문서 4-2 검증 결과
  ```
- 출력:

  ```json
  {
    "guide_id": 77,
    "passed": false,
    "fail_reasons": [
      { "type": "value_mismatch", "drug_name": "가상정 5mg", "prescription_item_id": 501, "item_id": null, "detail": "times_per_day 2 ≠ 처방 3" },
      { "type": "forbidden", "drug_name": "가상정 5mg", "prescription_item_id": 501, "item_id": "d1-c2", "detail": "복용 중단 권유 표현" }
    ],
    "item_checks": {},
    "fallback_drug_ids": [],
    "attempt_no": 1,
    "rules_version": "verify_rules_v1",
    "prompt_version": "guide_medication_v1",
    "duration_ms": 180,
    "checked_at": "2026-11-20T18:30:05+09:00"
  }
  ```

  `is_last_attempt=True`이고 실패하면:

  ```json
  {
    "passed": false,
    "item_checks": { "d1-c2": "fallback" },
    "fallback_drug_ids": [501]
  }
  ```
  (나머지 칸은 위와 같음)

- 1차 검사 규칙(AI 문서 11-2):

  | 규칙 | 무엇을 | 실패 `type` |
  | --- | --- | --- |
  | VERI-001 원문 대조 | `dose_per_time`·`times_per_day`·`total_days`·`dose_times[]`를 `prescription_item_id`로 짝지어 비교. 용량은 AI 문서 4-9 방식 | `value_mismatch`, `missing_value` |
  | VERI-001 글 속 숫자 | `easy_text` 안의 숫자·'하루 두 번' 같은 표현. 처방 용량이 `parsed: false`인데 용량 숫자가 나오면 실패 | `text_number_mismatch` |
  | VERI-002 빠진 약 | 가이드 `drugs[]`의 `prescription_item_id` 집합이 처방과 같은지 | `missing_drug` |
  | VERI-003 1차 | `has_public_data`를 약품 DB로 다시 판정. `false`인 약에 주의사항·부작용·병원 방문 항목이 있으면 실패 | `no_source` |
  | VERI-004 금지 표현 | ⓐ 복용 중단·용량 변경·약 대체 권유 ⓑ 처방에 없는 약 이름 ⓒ 기저질환에 없는 질환을 단정하는 표현. 공공데이터 원문 인용·병원 방문 고정 문구는 예외 | `forbidden`, `unknown_drug` |
- 에러: 규칙 위반은 예외를 던지지 않고 `passed: false`로 돌려줍니다. 가이드 JSON 모양이 깨졌으면 `missing_value`로 돌려줍니다. 함수 내부 오류만 예외(`VerifyError`)를 던지며, 이때 호출하는 쪽은 AI 오류 1회로 셉니다.
- 비고:
  - 1차의 `item_checks`는 `fallback`만 채웁니다(빈 값이면 화면 표시 안 함). `verified`·`needs_check`는 2차(VERI-006)입니다.
  - `fallback_drug_ids`는 AI 문서 4-2에 없는 칸으로 새로 제안합니다. 약 단위 실패(`item_id: null`: 숫자 불일치, 빠진 약)가 남은 약의 ID이며, 가이드 생성 쪽이 그 약의 설명을 약 기본 정보(MED-003) + "이 부분은 의사·약사에게 확인해 주세요"로 바꿔 끼웁니다 → 유정님 확인.
  - 목표 시간: 1건 1초(내부 목표), 5초 이내(NFR-014). 15초 한도 안에 검사 시간이 포함되므로 `duration_ms`를 꼭 채웁니다.
  - 금지 표현·약 이름 목록은 AI B의 응급·범위 밖 목록과 같은 단어 검사 기능을 씁니다(AI 문서 C6).


<!-- 채민 END -->

---

<!-- 유정 START · 가이드·챗봇 -->
## 7. 가이드·챗봇 (AI B)

담당: 유정 · 관련 화면: D-1, D-2, C-1(가이드 보기), F-1 · 관련 테이블: `guides`, `prompt_versions`, `rag_documents`, `chat_sessions`, `chat_messages`

> AI 파트 기획 문서 v5의 6-1(AI B), 6-3, 6-4, 4-1, 4-4, 4-5를 1-4 양식으로 옮겨 적습니다.

| 확인할 것 | 같이 볼 사람 |
| --- | --- |
| 가이드 진행 상태에 `failed`가 필요합니다(AI 문서 4-4, D2). ERD `guide_status`에는 아직 없습니다 | 민정 |
| 가이드는 처방 확정 시 `start_guide_generation()`으로 자동 생성되므로, 화면에서 부르는 생성 요청 API는 따로 두지 않습니다 | 채민 · 설아 |
| 생성에 실패하면 약 기본 정보를 보여 주고, [다시 시도](`/guides/retry`)로 한 번 더 생성합니다. 30초 안에 끝나지 않으면 실패로 처리합니다. 자동 재시도·세부 시간 기준은 2차입니다(11/20 결정) | 설아 |
| 검증 실패를 줄이기 위해 숫자(용량·횟수·일수·복용 시각)와 약 목록 틀은 확정 처방에서 코드로 채우고, LLM은 설명 칸만 씁니다 | 채민 |
| 이전 대화 목록·내용 조회는 2차(CHAT-003)입니다. 1차는 대화방만 만들고 목록은 숨깁니다(AI 문서 D23) | 설아 |
| SSE 이벤트는 1-3 표를 따릅니다 | 설아 |
| 공공데이터 `drugs` 적재를 RAG 수집과 같은 파이프라인에서 처리합니다. 컬럼은 ERD `drugs`를 따르고, 데이터 기준일(`data_fetched_at`)을 함께 저장합니다 | 민정 · 채민(약품 매칭) |

<!-- 유정 END -->

---

## 8. 팀 확인 요청

| No | 내용 | 확인할 사람 |
| --- | --- | --- |
| 1 | ✅ 공통 규칙(1번) 확정: 에러 코드 목록, 상태 조회 간격(2초), 토큰 만료 시간(액세스 30분 / 리프레시 14일)(11/20) | 민정 |
| 2 | ✅ 추가 정보 미입력·필수 약관 미동의는 `PROFILE_REQUIRED`(403)로 처리하고, 예외 API를 1-1에 적었습니다(11/20) | 민정 |
| 3 | 개발 중에는 FastAPI Swagger(`/docs`)와 이 문서를 대조하고, 기능이 끝나면 문서를 최신 상태로 맞춥니다 | 전원 |
| 4 | ✅ 처방 직접 입력(MED-001)은 2차에서 1차(축소 유지)로 올립니다. OCR이 실패해도 시연을 이어 가고, OCR 없이 테스트 데이터를 만들기 위함입니다(11/20) | 전원 |
| 5 | ✅ 처방 저장은 `create_prescription()` 하나로 통일하고 민정님이 맡습니다. 약 검색은 `GET /drugs?q=`로 합치고 채민님이 맡습니다(11/20) | 민정 · 채민 |

---

## 9. 변경 이력

| 날짜 | 작성자 | 내용 |
| --- | --- | --- |
| 2026-11-20 | 설아 | 초안 작성: 공통 규칙, 작성 양식, 예시, 1차 API 목록, 담당 배정 |
| 2026-11-20 | 설아 | API가 아닌 작업 분담 추가(3-1): 공공데이터 적재 → 유정, 프론트 배포 → 설아, 공통 테이블·백엔드 배포 → 민정 |
| 2026-11-20 | 설아 | AI 파트 기획 문서 v5 반영: 챗봇 담당을 유정으로 정정, AI API 이름·SSE 이벤트를 AI 문서 기준으로 변경, 처방 조회를 설아·복용 조건 확인을 채민으로 이동 |
| 2026-11-20 | 민정 | 공통 규칙 확정: 다른 회원 데이터는 `404`, 기본키는 `{대상}_id`, 토큰 액세스 30분 / 리프레시 14일 |
| 2026-11-20 | 민정 | 1-1 `PROFILE_REQUIRED`에 필수 약관 동의 포함, 예외 API 명시(`/auth/*`, `GET /users/me`, `POST /users/me/profile`) |
| 2026-11-20 | 민정 | 8번 1·2 확정 |
| 2026-11-20 | 설아 | 처방 직접 입력(MED-001) 1차 반영: `POST /prescriptions`, 내부 함수 `create_prescription()` 추가(민정), 확정 API는 이 함수를 호출하도록 변경 |
| 2026-11-20 | 설아 | 약 검색 통합: `/drugs/search?name=` → `/drugs?q=&limit=`(채민), 직접 입력 검색과 공용 |
