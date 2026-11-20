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
3. 작업 전에 `git pull origin dev`로 최신 내용을 받고, 브랜치는 `docs/api-영역`(예: `docs/api-ocr`)으로 만듭니다.
4. PR 제목은 `docs: API 명세서 ○○ 작성`으로 통일합니다.
5. 다른 영역에 필요한 API가 보이면 직접 쓰지 않고, 담당자에게 말하거나 자기 섹션에 "→ ○○님 확인"이라고 적습니다.
6. 3번 목록의 **상태**도 같이 바꿉니다: `작성 전` → `작성 중` → `리뷰 요청` → `확정`
7. 공통 규칙(1번)을 바꿔야 하면 민정님께 먼저 말씀드리고, 바꾼 내용은 9번 변경 이력에 남깁니다.

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

경로 앞의 `/api/v1`은 생략했습니다. AI 파트가 먼저 정리한 API는 AI 파트 기획 문서 6장의 이름을 그대로 가져왔습니다. 합계 26개 + 내부 함수 3개입니다(민정 9 · 채민 7+내부 1 · 유정 6+내부 1 · 설아 4, 나머지 내부 1개는 8번 확인 요청).

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
| 홈 | GET | `/home/today` | 원형 약통 화면 데이터 한 번에 | MED-016·017 | A-2 | 설아 | 작성 전 |
| 약 정보 | GET | `/drugs/{drug_id}` | 약 상세(공공데이터) | MED-002 | C-2 | 설아 | 작성 전 |
| 처방 | GET | `/prescriptions` | 처방 목록(복용 중 / 종료) | MED-002 | C-1 | 설아 | 작성 전 |
| 처방 | GET | `/prescriptions/{prescription_id}` | 처방 상세(약·복용 조건·시간표) | MED-002 | C-1 | 설아 | 작성 전 |
| 처방 등록 | POST | `/scans` | 처방전·약봉투 파일 업로드 → 읽기 시작(202) | OCR-001·002 | B-1 | 채민 | 작성 전 |
| 처방 등록 | GET | `/scans/{scan_id}` | 진행 상태 또는 인식 결과 | OCR-002·003·004 | B-1, B-2 | 채민 | 작성 전 |
| 처방 등록 | PATCH | `/scans/{scan_id}` | 인식 결과 수정·문서 종류 다시 고르기 | OCR-001·004 | B-2 | 채민 | 작성 전 |
| 처방 등록 | GET | `/scans/{scan_id}/pages/{page_no}/image` | 원본 페이지 이미지 | OCR-004 | B-2 | 채민 | 작성 전 |
| 처방 등록 | POST | `/scans/{scan_id}/confirm` | 확정 → 처방 저장 → 원본 삭제 → 가이드 생성 시작 | OCR-004 | B-2 | 채민 | 작성 전 |
| 처방 등록 | GET | `/drugs/search?name=` | 약품 매칭 후보(최대 3개) | OCR-005 | B-2 | 채민 | 작성 전 |
| 처방 등록 | PATCH | `/dose-conditions/{condition_id}` | '복용 조건 확인 필요' 항목을 회원이 고름 | MED-008 | B-2 | 채민 | 작성 전 |
| 가이드 | GET | `/prescriptions/{prescription_id}/guides` | 복약·생활습관 가이드 보기(만드는 중이면 진행 상태) | GUIDE-001·002·004·006·007 | D-2, C-1 | 유정 | 작성 전 |
| 가이드 | POST | `/prescriptions/{prescription_id}/guides/retry` | 실패 화면의 [다시 시도] | GUIDE-007 | D-2 | 유정 | 작성 전 |
| 가이드 | GET | `/guides` | 내 가이드 목록 | GUIDE-004 | D-1 | 유정 | 작성 전 |
| 챗봇 | GET | `/chat/suggestions` | 추천 질문 3개 | CHAT-001 | F-1 | 유정 | 작성 전 |
| 챗봇 | POST | `/chat/sessions` | 채팅창을 열 때 새 대화 만들기 | CHAT-001 | F-1 | 유정 | 작성 전 |
| 챗봇 | POST | `/chat/sessions/{session_id}/messages` | 질문 보내기 → 답변(SSE) | CHAT-001·002·004·005, VERI-004 | F-1 | 유정 | 작성 전 |
| 내부 | - | `verify_guide()` | 가이드 검증(원문 대조·빠진 약·금지 표현) | VERI-001·002·004 | - | 채민 | 작성 전 |
| 내부 | - | `start_guide_generation()` | 처방 확정 후 가이드 생성 시작(비동기) | GUIDE-001·002 | - | 유정 | 작성 전 |
| 내부 | - | `get_confirmed_prescription()` | 확정 처방 + 회차별 복용 조건 조회 | OCR-004, MED-008 | - | 미정 | 작성 전 |

---

### 3-1. API가 아닌 작업 분담

API 개수만으로는 보이지 않는 작업을 함께 나눕니다.

| 작업 | 담당 | 내용 |
| --- | --- | --- |
| 공통 규칙·인증 미들웨어 | 민정 | 1번 공통 규칙 확정, JWT 인증·`PROFILE_REQUIRED` 처리 |
| 공통 테이블 | 민정 | `users`, `prescriptions`, `prescription_items`, `dose_conditions`처럼 여러 사람이 쓰는 테이블의 모델·마이그레이션을 먼저 올립니다. 나머지 테이블은 각자 자기 API가 쓰는 테이블을 만듭니다 |
| 시간표 계산·복용 기록 생성 | 민정 | 처방 확정 후 기본 일과로 `dose_schedules` 계산, `intake_logs` 생성 |
| 공공데이터 `drugs` 적재 | 유정 | RAG용 e약은요 데이터를 받을 때 `drugs` 테이블에도 함께 넣습니다. 같은 데이터를 두 번 받지 않도록 한 파이프라인으로 처리합니다 |
| 백엔드 배포 | 민정 | EC2 + Docker Compose (NFR-007) |
| 프론트 배포 | 설아 | 프론트는 백엔드와 따로 배포합니다(Vercel 등). 백엔드 주소 연결 방식은 민정님과 맞춥니다 |

---

<!-- 민정 START · 인증·회원 -->
## 4. 인증·회원 / 복용 기록

담당: 민정 · 관련 화면: A-1, A-2, E-1, E-2 · 관련 테이블: `users`, `user_consents`, `refresh_tokens`, `health_profiles`, `user_conditions`, `intake_logs`, `daily_flowers`

> 1-4 양식을 복사해서 작성합니다.

| 확인할 것 | 같이 볼 사람 |
| --- | --- |
| 첫 로그인 응답에 `is_profile_completed`를 포함합니다. `false`이면 프론트가 추가 정보 입력 화면으로 이동하고, 그 전에는 다른 API가 `PROFILE_REQUIRED`를 돌려줍니다 | 설아 |
| 건강 프로필 항목은 가이드·챗봇 개인화 입력이라, 필드 이름을 정할 때 유정님과 맞춥니다 | 유정 |
| 복용 체크는 2번 예시를 이어서 확정합니다 | 설아 |
| 처방 확정 시 복용 기록(`intake_logs`)을 언제부터 만들지(등록 시각 이후 회차부터) | 채민 |
| `drugs` 테이블 컬럼은 ERD 기준으로 먼저 정해 두고, 적재는 유정님이 맡습니다 | 유정 |

<!-- 민정 END -->

---

<!-- 설아 START · 홈·약 정보 -->
## 5. 홈·약 정보·처방 조회

담당: 설아 · 관련 화면: A-2, C-1, C-2 · 관련 테이블: `intake_logs`, `dose_schedules`, `daily_flowers`, `drugs`, `prescriptions`, `prescription_items`, `dose_conditions`

> 1-4 양식을 복사해서 작성합니다.

| 확인할 것 | 같이 볼 사람 |
| --- | --- |
| `/home/today`에 담을 값: 오늘 날짜, 회차 목록(시각·라벨·칸 상태 `done / due / missed`·약 목록), 필요시 약, 요일 미니 약통(7일 완료율), 오늘 꽃 상태, 다음 복용 시각, 기본 일과 사용 여부 | 민정 |
| 약 상세 하단에 데이터 기준일(`drugs.data_fetched_at`)을 표시합니다 | - |
| 1차 시간표는 기본 일과(기상 07:00 / 식사 08:00·12:30·18:30 / 취침 23:00)로 계산합니다. 처방 상세 응답에 회차별 시각과 `schedule_status`를 넣습니다 | 민정 |

<!-- 설아 END -->

---

<!-- 채민 START · 처방 등록·검증 -->
## 6. 처방 등록·검증 (AI A)

담당: 채민 · 관련 화면: B-1, B-2 · 관련 테이블: `medical_documents`, `document_pages`, `drugs`, `prescriptions`·`prescription_items`·`dose_conditions`(확정 시 생성)

> AI 파트 기획 문서 v5의 6-1(AI A), 4-3, 4-10, 11-2를 1-4 양식으로 옮겨 적습니다.

| 확인할 것 | 같이 볼 사람 |
| --- | --- |
| 확정 API를 AI A가 맡을지 백엔드가 맡을지(AI 문서 D11). 확정과 동시에 처방 저장·원본 삭제·가이드 생성 시작이 일어납니다 | 민정 · 유정 |
| 진행 상태 값: AI 문서(`reading / structuring / ready / failed / expired`)와 ERD `document_status`(`uploaded / ocr_done / ocr_failed / confirmed / expired`)가 다릅니다. 한쪽으로 맞춥니다 | 민정 · 설아 |
| 칸별 신뢰도 `{value, confidence, needs_check}`로 확인 화면의 노란색 강조를 표시합니다 | 설아 |
| `verify_guide()` 입력·출력은 AI 문서 4-1·4-2 형식을 따릅니다 | 유정 |

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
| 생성에 실패하면 약 기본 정보를 보여 주고, [다시 시도](`/guides/retry`)로 한 번 더 생성합니다. 자동 재시도·시간 기준은 2차입니다(11/20 결정) | 설아 |
| 이전 대화 목록·내용 조회는 2차(CHAT-003)입니다. 1차는 대화방만 만들고 목록은 숨깁니다(AI 문서 D23) | 설아 |
| SSE 이벤트는 1-3 표를 따릅니다 | 설아 |
| 공공데이터 `drugs` 적재를 RAG 수집과 같은 파이프라인에서 처리합니다. 컬럼은 ERD `drugs`를 따르고, 데이터 기준일(`data_fetched_at`)을 함께 저장합니다 | 민정 · 채민(약품 매칭) |

<!-- 유정 END -->

---

## 8. 팀 확인 요청

| No | 내용 | 확인할 사람 |
| --- | --- | --- |
| 1 | 공통 규칙(1번) 확정: 에러 코드 목록, 상태 조회 간격(2초), 토큰 만료 시간 | 민정 |
| 2 | 동의 없음·추가 정보 미입력을 403으로 둘지 다른 코드로 둘지 | 민정 |
| 3 | 개발 중에는 FastAPI Swagger(`/docs`)와 이 문서를 대조하고, 기능이 끝나면 문서를 최신 상태로 맞춥니다 | 전원 |
| 4 | AI 파트 문서(11/19)와 1차 축소안(11/20)이 다른 부분: 검증 재생성(VERI-005)·LLM 복용법 해석·수동 등록(MED-001)·직접 입력 복용법 해석(`POST /dosage/parse`)이 AI 문서에는 1차, 축소안에는 2차입니다. 투여 주기·감량 단계(MED-012·013)는 11/19 범위 축소에서 제외됐습니다. 이번 회의에서 1차 범위를 하나로 맞춥니다 | 채민 · 유정 · 전원 |
| 5 | 주소 앞부분: AI 문서는 `/api/...`, 이 문서는 `/api/v1/...`입니다. 공통 규칙(1번)을 따르는 것으로 맞춥니다 | 민정 · 채민 · 유정 |
| 6 | `get_confirmed_prescription()`을 AI A가 만들지 백엔드가 만들지(AI 문서 D11과 함께 결정) | 민정 · 채민 |

---

## 9. 변경 이력

| 날짜 | 작성자 | 내용 |
| --- | --- | --- |
| 2026-11-20 | 설아 | 초안 작성: 공통 규칙, 작성 양식, 예시, 1차 API 목록, 담당 배정 |
| 2026-11-20 | 설아 | API가 아닌 작업 분담 추가(3-1): 공공데이터 적재 → 유정, 프론트 배포 → 설아, 공통 테이블·백엔드 배포 → 민정 |
| 2026-11-20 | 설아 | AI 파트 기획 문서 v5 반영: 챗봇 담당을 유정으로 정정, AI API 이름·SSE 이벤트를 AI 문서 기준으로 변경, 처방 조회를 설아·복용 조건 확인을 채민으로 이동 |
