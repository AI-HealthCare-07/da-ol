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
| 처방 등록 | POST | `/scans` | 처방전·약봉투 파일 업로드 → 읽기 시작(202) | OCR-001·002 | B-1 | 채민 | 작성 전 |
| 처방 등록 | GET | `/scans/{scan_id}` | 진행 상태 또는 인식 결과 | OCR-002·003·004 | B-1, B-2 | 채민 | 작성 전 |
| 처방 등록 | PATCH | `/scans/{scan_id}` | 인식 결과 수정·문서 종류 다시 고르기 | OCR-001·004 | B-2 | 채민 | 작성 전 |
| 처방 등록 | GET | `/scans/{scan_id}/pages/{page_no}/image` | 원본 페이지 이미지 | OCR-004 | B-2 | 채민 | 작성 전 |
| 처방 등록 | POST | `/scans/{scan_id}/confirm` | 확정 → `create_prescription()` 호출 → 원본 삭제 | OCR-004 | B-2 | 채민 | 작성 전 |
| 약 정보 | GET | `/drugs?q=&limit=` | 약 검색(OCR 매칭 후보는 `limit=3`, 직접 입력 검색은 기본 10) | OCR-005, MED-001 | B-2, B-1(직접 입력) | 채민 | 작성 전 |
| 처방 등록 | PATCH | `/dose-conditions/{condition_id}` | '복용 조건 확인 필요' 항목을 회원이 고름 | MED-008 | B-2 | 채민 | 작성 전 |
| 가이드 | GET | `/prescriptions/{prescription_id}/guides` | 복약·생활습관 가이드 보기(만드는 중이면 진행 상태) | GUIDE-001·002·004·006·007 | D-2, C-1 | 유정 | 리뷰 요청 |
| 가이드 | POST | `/prescriptions/{prescription_id}/guides/retry` | 실패 화면의 [다시 시도] | GUIDE-007 | D-2 | 유정 | 리뷰 요청 |
| 가이드 | GET | `/guides` | 내 가이드 목록 | GUIDE-004 | D-1 | 유정 | 리뷰 요청 |
| 챗봇 | GET | `/chat/suggestions` | 추천 질문 3개 | CHAT-001 | F-1 | 유정 | 리뷰 요청 |
| 챗봇 | POST | `/chat/sessions` | 채팅창을 열 때 새 대화 만들기 | CHAT-001 | F-1 | 유정 | 리뷰 요청 |
| 챗봇 | POST | `/chat/sessions/{session_id}/messages` | 질문 보내기 → 답변(SSE) | CHAT-001·002·004·005, VERI-004 | F-1 | 유정 | 리뷰 요청 |
| 내부 | - | `verify_guide()` | 가이드 검증(원문 대조·빠진 약·금지 표현) | VERI-001·002·004 | - | 채민 | 작성 전 |
| 내부 | - | `start_guide_generation()` | 처방 확정 후 가이드 생성 시작(비동기) | GUIDE-001·002 | - | 유정 | 리뷰 요청 |
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

| 확인할 것 | 같이 볼 사람 |
| --- | --- |
| ✅ 확정 API는 채민님이 맡고, 저장은 민정님의 `create_prescription()`을 부릅니다(AI 문서 D11, 11/20). 채민님은 인식 결과를 이 함수의 입력 형식으로 넘기고 원본을 삭제합니다 | 민정 · 유정 |
| 약 검색은 `GET /drugs?q=&limit=` 하나로 처리합니다. OCR 매칭 후보는 `limit=3`, 직접 입력(MED-001) 검색은 기본 10개로 같은 API를 씁니다. 상품명·성분명 모두 검색됩니다 | 민정 · 설아 |
| 진행 상태 값: AI 문서(`reading / structuring / ready / failed / expired`)와 ERD `document_status`(`uploaded / ocr_done / ocr_failed / confirmed / expired`)가 다릅니다. 한쪽으로 맞춥니다 | 민정 · 설아 |
| 칸별 신뢰도 `{value, confidence, needs_check}`로 확인 화면의 노란색 강조를 표시합니다 | 설아 |
| `verify_guide()` 입력·출력은 AI 문서 4-1·4-2 형식을 따릅니다 | 유정 |

<!-- 채민 END -->

---

<!-- 유정 START · 가이드·챗봇 -->
## 7. 가이드·챗봇 (AI B)

담당: 유정 · 관련 화면: D-1, D-2, C-1(가이드 보기), F-1 · 관련 테이블: `guides`, `prompt_versions`, `llm_call_logs`, `rag_documents`, `chat_sessions`, `chat_messages`, `drugs`(실패 시 기본 정보) · 내부 함수: `start_guide_generation()`

> AI 파트 기획 문서 v5의 6-1(AI B), 6-3, 6-4, 4-1, 4-4, 4-5와 백엔드 전달사항(`전달사항_AI.md`, 11/19)을 1-4 양식으로 옮겨 적습니다.
> 1차 축소안(11/20)에 맞춰 자동 재시도·틀린 약 다시 쓰기(VERI-005)·다시 만들기(GUIDE-005)·피드백(GUIDE-008)·이전 대화(CHAT-003)·하루 사용량(CHAT-006)은 2차로 뺐습니다.

| 확인할 것 | 같이 볼 사람 |
| --- | --- |
| ✅ 가이드 진행 상태에 `failed`가 추가됐습니다(1차 ERD, 11/20). 실패해도 행을 남기고 `status = failed`, `content = NULL`로 두며, [다시 시도]는 같은 행을 `generating`으로 되돌립니다 | 민정 · 설아 |
| 가이드는 `create_prescription()`이 마지막에 `start_guide_generation()`을 불러 자동으로 시작합니다. 화면에서 부르는 생성 요청 API는 따로 두지 않습니다(사진 확정·직접 입력 공통) | 민정 · 채민 · 설아 |
| 1차 실패 처리: 검증에서 틀린 항목은 약 기본 정보로 바꾸고 '확인 필요'를 붙입니다(`completed_with_replacements`). LLM 오류·시간 초과는 `failed` + [다시 시도]입니다. 자동 재시도·틀린 약 다시 쓰기·`is_retrying`은 2차입니다(1차 축소안 VERI-005·GUIDE-007) | 채민 · 설아 |
| ✅ 시간 기준: 1차는 "30초 안에 안 끝나면 `failed`" 한 가지만 둡니다(와이어프레임 D-2). 세부 시간 기준·자동 재시도는 2차입니다 | 설아 |
| 검증 실패를 줄이기 위해 숫자(용량·횟수·일수·복용 시각)와 약 목록 틀은 확정 처방에서 코드로 채우고, LLM은 설명 칸만 씁니다 | 채민 |
| 복용 시각: 1차는 기본 일과로 계산한 `dose_schedules`(weekday 한 행)를 그대로 씁니다. `needs_check`인 회차는 시각을 비우고 "복용 시간 확인 필요"로 둡니다(백엔드 전달사항 3-3은 생활 일과가 2차로 내려가 1차에서는 해당 없음) | 민정 · 설아 |
| **SSE 이벤트는 이 섹션(7-6)을 기준으로 해 주세요.** 1-3 표는 백엔드 합의(전달사항 2-4) 전 이름이라 수정이 필요합니다: `token` → `delta`, `message` → `text`, 응급 `type`은 `physical` / `self_harm` + `call`(`119` / `109`), `done`은 API가 보냄 | 설아 · 민정 |
| 생활습관 가이드도 `verify_guide()`를 거칩니다. 약 숫자가 없으므로 금지 표현(VERI-004)만 검사하는 안입니다 → 채민님 확인 | 채민 |
| 챗봇 금지 표현(VERI-004) 1차: 시스템 프롬프트로 막고, 답변이 끝난 뒤 검사 결과는 기록만 합니다. 화면 정정 안내(`correction` 이벤트)는 2차(VERI-007)입니다 | 채민 |
| 챗봇 질문은 저장 전에 개인정보 가리기 함수(`mask_text()`, 채민)를 거칩니다. 3-1 표에 이 함수 담당을 추가해 주세요 | 채민 · 민정 |
| 이전 대화 목록·내용 조회는 2차(CHAT-003)입니다. 1차는 채팅창을 열 때마다 대화방을 만들고 목록은 숨깁니다(AI 문서 D23) | 설아 |
| 공공데이터 `drugs` 적재를 RAG 수집과 같은 파이프라인에서 처리합니다. 컬럼은 ERD `drugs`를 따르고, 데이터 기준일(`data_fetched_at`)을 함께 저장합니다 | 민정 · 채민(약품 매칭) |
| 공용 테스트 처방 시나리오 10건(NFR-011)은 재경님이 `docs/test-prescriptions/`에 작성합니다(11/20 공지). 가이드·챗봇은 이 시나리오로 결과(처방에 없는 약·변경 권유·면책 문구 누락)를 확인합니다 | 재경 · 채민 |

### 7-1. [GET] /api/v1/prescriptions/{prescription_id}/guides
- 설명: 처방 하나의 복약 가이드와 생활습관 가이드를 함께 돌려줍니다. 아직 만드는 중이면 진행 상태만 돌려주고, 화면은 2초마다 다시 부릅니다(1-2). 저장된 가이드가 있으면 LLM을 다시 부르지 않습니다(GUIDE-004).
- 인증: 필요
- 관련 요구사항: REQ-GUIDE-001·002·004·006·007, REQ-VERI-005
- 관련 화면: D-2 가이드 보기, C-1 처방 상세(가이드 보기 버튼)
- 관련 테이블: `guides`, `drugs`(실패 시 기본 정보), `prompt_versions`
- Path / Query: Path `prescription_id`(`prescriptions.id`)
- Request Body: 없음
- Response Body (200, 완성):

  ```json
  {
    "prescription_id": 123,
    "is_outdated": false,
    "used_default_profile": false,
    "disclaimer": "본 안내는 참고용이며, 의사·약사의 진료와 복약지도를 대체하지 않습니다.",
    "medication": {
      "guide_id": 9001,
      "status": "completed_with_replacements",
      "created_at": "2026-11-20T09:01:10+09:00",
      "content": {
        "drugs": [
          {
            "prescription_item_id": 502,
            "drug_name": "가상캡슐",
            "has_public_data": true,
            "how_to_take": {
              "dose_per_time": { "text": "1캡슐", "min": 1, "max": 1, "unit": "캡슐", "parsed": true },
              "times_per_day": 2,
              "total_days": 30,
              "dose_times": ["08:30", "19:00"],
              "easy_text": "하루 두 번, 아침과 저녁 식사 후 30분에 1캡슐씩 드세요."
            },
            "cautions": [
              { "item_id": "d1-c1", "text": "…", "sources": [{ "rag_document_id": 15, "name": "의약품개요정보(e약은요): 가상캡슐" }], "check": null }
            ],
            "side_effects": [
              { "item_id": "d1-s1", "symptom": "…", "what_to_do": "…", "sources": [{ "rag_document_id": 15, "name": "의약품개요정보(e약은요): 가상캡슐" }], "check": null }
            ],
            "see_doctor_if": [
              { "item_id": "d1-h1", "text": "…", "sources": [{ "rag_document_id": 15, "name": "의약품개요정보(e약은요): 가상캡슐" }], "check": "fallback" }
            ]
          }
        ],
        "sources": [{ "rag_document_id": 15, "name": "의약품개요정보(e약은요): 가상캡슐", "data_fetched_at": "2026-11-20" }]
      }
    },
    "lifestyle": {
      "guide_id": 9002,
      "status": "completed",
      "created_at": "2026-11-20T09:01:10+09:00",
      "content": {
        "diet": [{ "item_id": "l-d1", "text": "…", "sources": [{ "rag_document_id": 31, "name": "…" }], "check": null }],
        "exercise": [],
        "sleep": [],
        "smoking_alcohol": [],
        "sources": [{ "rag_document_id": 31, "name": "…" }]
      }
    }
  }
  ```
- Response Body (200, 만드는 중):

  ```json
  {
    "prescription_id": 123,
    "medication": { "guide_id": 9001, "status": "verifying" },
    "lifestyle": { "guide_id": 9002, "status": "generating" }
  }
  ```
- Response Body (200, 실패):

  ```json
  {
    "prescription_id": 123,
    "disclaimer": "본 안내는 참고용이며, 의사·약사의 진료와 복약지도를 대체하지 않습니다.",
    "medication": {
      "guide_id": 9001,
      "status": "failed",
      "fallback": {
        "drugs": [
          { "prescription_item_id": 502, "drug_name": "가상캡슐", "efficacy": "…", "usage_text": "…", "precautions": "…", "data_fetched_at": "2026-11-20" }
        ]
      }
    },
    "lifestyle": { "guide_id": 9002, "status": "failed" }
  }
  ```
- 에러: `NOT_FOUND`(404) 없는 처방·다른 회원의 처방 → 처방 목록으로 이동
- 비고:
  - `status` 값과 화면

    | 값 | 화면 |
    | --- | --- |
    | `generating` | "가이드를 만들고 있어요" |
    | `verifying` | "내용을 확인하고 있어요" |
    | `completed` | 가이드 표시 |
    | `completed_with_replacements` | 가이드 표시. `check: "fallback"`인 문장 옆에 '확인 필요' + "이 부분은 의사·약사에게 확인해 주세요" |
    | `failed` | `fallback`의 약 기본 정보 + "가이드를 만들지 못했어요. 잠시 후 다시 시도해 주세요" + [다시 시도] |
  - 화면은 두 가이드가 모두 `completed`, `completed_with_replacements`, `failed` 중 하나가 되면 폴링을 멈춥니다. 시작 후 30초가 지나면 서버가 `failed`로 바꿉니다.
  - 용량·횟수·일수·복용 시각은 확정 처방(`get_confirmed_prescription()`)에서 그대로 복사합니다. LLM이 만들지 않습니다.
  - `dose_times`는 **조회할 때** `dose_schedules`의 현재 시각으로 채웁니다. 확정 후 복용 조건을 바꿔도(`PATCH /dose-conditions`) 가이드와 시간표가 어긋나지 않게 하기 위함입니다(6장 채민님 제안). 필요시 약과 `needs_check` 회차는 빈 목록입니다.
  - `has_public_data: false`(약품 매칭 실패)인 약은 복용 방법만 보여 주고 "이 약은 안내 정보가 없어요"를 표시합니다.
  - `check`는 1차에 `null`(표시 없음)과 `fallback`(확인 필요)만 씁니다. '출처 확인됨'(`verified`)은 2차(VERI-006)입니다.
  - `used_default_profile: true`이면 상단에 "건강 프로필을 입력하면 더 정확한 안내를 받을 수 있어요"를 표시합니다(GUIDE-002).
  - `content.sources`는 화면 하단 출처 목록입니다. 문장별 출처에서 겹치는 것을 뺀 목록이고, 실제로 문장에 쓴 근거만 넣습니다(GUIDE-003).
  - 면책 문구는 `disclaimer` 값을 그대로 고정 표시합니다(GUIDE-006).

### 7-2. [POST] /api/v1/prescriptions/{prescription_id}/guides/retry
- 설명: 실패 화면의 [다시 시도]. `failed`인 가이드만 다시 만듭니다.
- 인증: 필요
- 관련 요구사항: REQ-GUIDE-007
- 관련 화면: D-2 가이드 보기(실패 상태)
- 관련 테이블: `guides`
- Path / Query: Path `prescription_id`
- Request Body: 없음
- Response Body (202):

  ```json
  {
    "prescription_id": 123,
    "medication": { "guide_id": 9001, "status": "generating" },
    "lifestyle": { "guide_id": 9002, "status": "completed" }
  }
  ```
- 에러: `NOT_FOUND`(404) 없는 처방·다른 회원의 처방 / `GUIDE_NOT_FAILED`(409) 실패한 가이드가 없음(이미 완성됐거나 만드는 중) → 7-1을 다시 불러 현재 상태 표시
- 비고:
  - 이후 진행 상태는 7-1로 확인합니다.
  - 내부에서는 실패한 가이드의 `guide_id`로 `run_guide_generation(guide_id)`를 다시 부릅니다(7-7).
  - 다시 시도는 2차 '다시 만들기 하루 3회'(GUIDE-005)에 세지 않습니다.

### 7-3. [GET] /api/v1/guides
- 설명: 내 가이드 목록. 최근 처방 순입니다.
- 인증: 필요
- 관련 요구사항: REQ-GUIDE-004
- 관련 화면: D-1 가이드 목록
- 관련 테이블: `guides`, `prescriptions`, `prescription_items`
- Path / Query: Query `page`, `size`(1번 공통 규칙)
- Request Body: 없음
- Response Body (200):

  ```json
  {
    "items": [
      {
        "prescription_id": 123,
        "hospital_name": "가상내과의원",
        "prescribed_date": "2026-11-20",
        "drug_count": 3,
        "status": "completed_with_replacements",
        "is_outdated": false,
        "created_at": "2026-11-20T09:01:10+09:00"
      }
    ],
    "page": 1,
    "size": 20,
    "total": 1
  }
  ```
- 에러: 공통 에러만 사용
- 비고:
  - `status`는 복약 가이드 기준입니다.
  - 가이드가 하나도 없으면 `items: []`이고, 화면은 "처방을 등록하면 가이드를 만들어 드려요"와 처방 등록 버튼을 보여 줍니다.

### 7-4. [GET] /api/v1/chat/suggestions
- 설명: 채팅창을 처음 열 때 보여 줄 추천 질문 3개
- 인증: 필요
- 관련 요구사항: REQ-CHAT-001
- 관련 화면: F-1 챗봇
- 관련 테이블: `prescriptions`, `prescription_items`(복용 중인 약 이름)
- Path / Query: 없음
- Request Body: 없음
- Response Body (200):

  ```json
  {
    "questions": [
      { "text": "가상정 먹고 술 마셔도 되나요?", "drug_name": "가상정" },
      { "text": "가상캡슐은 식전에 먹어도 되나요?", "drug_name": "가상캡슐" },
      { "text": "함께 피해야 할 음식이 있나요?", "drug_name": null }
    ]
  }
  ```
- 에러: 공통 에러만 사용
- 비고:
  - LLM을 쓰지 않고, 틀 문장에 복용 중인 약 이름을 넣어 만듭니다(예: "{약 이름} 먹고 술 마셔도 되나요?"). 틀 문장과 기본 질문은 AI 파트가 정합니다.
  - 복용 중인 약이 없으면 기본 질문 3개를 돌려줍니다.
  - 추천 질문을 누르면 7-6을 `is_recommended_question: true`로 부릅니다.

### 7-5. [POST] /api/v1/chat/sessions
- 설명: 채팅창을 열 때 새 대화방을 만듭니다.
- 인증: 필요
- 관련 요구사항: REQ-CHAT-001
- 관련 화면: F-1 챗봇
- 관련 테이블: `chat_sessions`
- Path / Query: 없음
- Request Body: 없음
- Response Body (201):

  ```json
  { "session_id": 77, "created_at": "2026-11-20T10:00:00+09:00" }
  ```
- 에러: 공통 에러만 사용
- 비고:
  - 1차는 대화 목록 화면이 없습니다. 채팅창을 열 때마다 새 대화방을 만들고, LLM에는 이 대화방의 최근 10턴만 보냅니다.
  - 대화방 제목(첫 질문 앞 20자)·목록·삭제는 2차(CHAT-003)입니다.

### 7-6. [POST] /api/v1/chat/sessions/{session_id}/messages
- 설명: 질문을 보내면 답변을 SSE(`text/event-stream`)로 조금씩 내려줍니다.
- 인증: 필요
- 관련 요구사항: REQ-CHAT-001·002·004·005, REQ-VERI-004
- 관련 화면: F-1 챗봇
- 관련 테이블: `chat_sessions`, `chat_messages`, `rag_documents`, `prompt_versions`, `llm_call_logs`
- Path / Query: Path `session_id`(`chat_sessions.id`)
- Request Body:

  ```json
  { "content": "지금 먹는 약이랑 가상진통정 같이 먹어도 되나요?", "is_recommended_question": false }
  ```
  `content`는 1~500자입니다.
- Response Body (200, SSE): 이벤트는 아래 표 순서로 내려갑니다. `meta`와 `done`은 API가 보내고, 나머지는 AI 모듈이 만들어 API가 그대로 흘려보냅니다(백엔드 전달사항 2-4).

  | 순서 | event | 보내는 쪽 | 언제 | data |
  | --- | --- | --- | --- | --- |
  | 0 | `meta` | API | 질문을 저장한 직후 | `{"user_message_id": 811, "masked_content": "…"}`. 화면은 방금 보낸 질문을 이 값으로 바꿔 보여 줍니다 |
  | 1 | `emergency` | AI | 응급 표현이 있을 때, LLM보다 먼저 | `{"type": "physical", "call": "119", "text": "…"}` 또는 `{"type": "self_harm", "call": "109", "text": "…"}`. `self_harm`이면 답변 없이 바로 `done` |
  | 1' | `out_of_scope` | AI | 답할 수 없는 질문 | `{"type": "diagnosis" / "prescription_change" / "unrelated", "text": "…"}` → 바로 `done` |
  | 2 | `delta` | AI | 답변 글자 조각(여러 번) | `{"text": "지금 드시는"}` |
  | 3 | `sources` | AI | 답변이 끝났을 때 | `{"items": [{"rag_document_id": 15, "name": "의약품개요정보(e약은요): 가상정"}]}` |
  | 4 | `done` | API | 마지막 | `{"message_id": 812, "show_profile_link": false}` |
  | - | `error` | AI | 도중에 실패 | `{"code": "EXTERNAL_API_ERROR", "message": "답변을 불러오지 못했어요. 다시 보내기를 눌러 주세요"}` |

  일반 질문 예시:

  ```text
  event: meta
  data: {"user_message_id": 811, "masked_content": "지금 먹는 약이랑 가상진통정 같이 먹어도 되나요?"}

  event: delta
  data: {"text": "가상진통정은 "}

  event: delta
  data: {"text": "지금 드시는 약과 …"}

  event: sources
  data: {"items": [{"rag_document_id": 15, "name": "의약품개요정보(e약은요): 가상정"}]}

  event: done
  data: {"message_id": 812, "show_profile_link": false}
  ```
- 에러: SSE를 열기 전에 막는 것 → `VALIDATION_ERROR`(422) 빈 질문·500자 초과 → 화면에서 먼저 막고(전송 버튼 비활성, 500자 넘게 입력 안 됨) 혹시 오면 "질문은 500자까지 입력할 수 있어요" / `NOT_FOUND`(404) 없는 대화방·다른 회원의 대화방 → 7-5로 새 대화방 만들기 / `ANSWER_IN_PROGRESS`(409) 앞 질문의 답변이 아직 나오는 중 → 전송 버튼 비활성. SSE 도중 실패는 `error` 이벤트로 보냅니다.
- 비고:
  - 처리 순서: ① 질문 가리기(`mask_text()`) 후 저장 → `meta` ② 응급 표현 확인(규칙, LLM 호출 전) ③ 범위 확인(1차는 키워드, 범위 밖이면 고정 문구, LLM 안 부름) ④ 근거 검색(복용 중인 약 + 질문에 나온 약) ⑤ LLM 답변(`delta`) ⑥ 금지 표현 검사(1차는 기록만) ⑦ `sources` ⑧ 답변 저장 → `done`
  - 프롬프트에는 복용 중인 약(이름·성분명·복용법 요약·복용 시각), 건강 프로필(이름·이메일 제외, 나이는 나이대로), 최근 10턴을 넣습니다(CHAT-002).
  - 건강 프로필이 없으면 약 정보만으로 답하고, 대화방에서 처음 한 번만 `show_profile_link: true`를 보냅니다.
  - 신체 응급(`physical`)은 빨간 카드로 119 안내를 먼저 보여 주고 이어서 답변합니다. 자해·자살(`self_harm`)은 109 안내만 보여 주고 일반 답변을 하지 않습니다(CHAT-004).
  - 범위 밖 안내는 LLM을 쓰지 않는 고정 문구입니다. '진료 준비에 추가' 버튼은 2차(MED-015)에 붙입니다.
  - 회원이 중간에 연결을 끊으면 API가 AI 생성을 닫고, AI는 LLM 호출도 함께 멈춥니다(비용).
  - ERD 저장 값: `physical` → `message_type: emergency_physical`, `self_harm` → `emergency_self_harm`, `out_of_scope` → `out_of_scope`, `error` → `status: failed`.
  - 하루 50개 제한(`RATE_LIMITED`)과 차감 규칙은 2차(CHAT-006)입니다.

### 7-7. 내부 함수: `start_guide_generation(prescription_id)`
- 설명: 확정된 처방으로 복약 가이드와 생활습관 가이드를 따로, 동시에 만들기 시작합니다. 바로 돌아오고, 실제 생성은 백그라운드에서 합니다.
- 부르는 곳: 민정님 `create_prescription()`의 마지막 단계(사진 확정·직접 입력 공통)
- 관련 요구사항: REQ-GUIDE-001·002·003·006·007, REQ-VERI-005, REQ-NFR-006
- 관련 테이블: `guides`, `prompt_versions`, `llm_call_logs`, `rag_documents`
- 입력: `prescription_id`
- 출력: 만든 `guide_id` 2개(`medication`, `lifestyle`). 진행 상태는 7-1로 확인합니다.
- 처리 순서:
  1. `guides`에 두 행을 `status = generating`으로 만들고, 가이드마다 `run_guide_generation(guide_id)`를 백그라운드로 실행합니다.
  2. 확정 처방(`get_confirmed_prescription()`, 설아), 건강 프로필, 복용 시각(`dose_schedules`)을 읽습니다.
  3. 근거 검색: 약마다 약품명으로 좁혀 검색하고 상위 5개를 씁니다(GUIDE-003).
  4. LLM으로 설명 칸을 씁니다. 숫자 칸은 확정 처방 값을 코드로 채웁니다.
  5. `status = verifying`으로 바꾸고 `verify_guide()`(채민)로 검증합니다.
  6. 통과 → `completed` / 틀린 항목이 있으면 그 항목을 약 기본 정보로 바꾸고 `check: "fallback"` → `completed_with_replacements` / LLM 오류·30초 초과 → `failed`(`content = NULL`)
- 비고:
  - 1차 실행 방식: API 서버 안의 백그라운드 작업(FastAPI `BackgroundTasks`)으로 돌립니다. 2차에 `ai_worker`로 옮길 때 같은 `run_guide_generation(guide_id)`를 그대로 부릅니다(백엔드 전달사항 2-3).
  - LLM을 부를 때마다 `llm_call_logs`에 목적·모델·토큰·응답 시간·성공 여부·프롬프트 버전을 남깁니다. 질문·답변 본문과 개인정보는 남기지 않습니다(NFR-004·006).
  - 프롬프트는 코드 파일로 두고 배포할 때 `prompt_versions`에 버전을 등록합니다(`guide_medication_v1`, `guide_lifestyle_v1`, `chat_v1`). Temperature는 0.1~0.2로 고정합니다(NFR-017).

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
| 2026-11-20 | 유정 | 7장 리뷰 반영: `failed`·30초 기준 확정 표시, 가이드 `dose_times`는 조회 때 시간표 값으로 채움(채민님 제안), 생활습관 가이드 검증 확인 요청 추가 |
| 2026-11-20 | 유정 | 7장 가이드·챗봇 작성: API 6개 + 내부 함수 1개. 1차 축소안 반영(자동 재시도·다시 만들기·피드백·이전 대화는 2차), SSE 이벤트는 백엔드 합의 이름(`delta`·`text`·`physical/self_harm`)으로 작성 |
