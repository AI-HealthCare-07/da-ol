# 다올 API 명세서 (1차)

> 기준 문서: 요구사항 정의서 1차 축소안(11/20) · ERD `daol_erd_phase1.dbml` · 와이어프레임(A-1 ~ F-1) · AI 파트 기획 문서 v5(AI A 채민님 / AI B 유정님)
> 자기가 구현할 API는 자기가 작성합니다. 팀장이 프론트 입장에서 전체를 리뷰하고, AI와 백엔드가 맞닿는 부분은 민정님이 리뷰합니다.
> 2·3차 API(화단·통계·상점·알림 등)는 1차가 동작한 뒤에 추가합니다.

| 담당 | 영역 | 섹션 |
| --- | --- | --- |
| 민정 | 공통 규칙 확정, 인증·회원·건강 프로필(명세), 복용 기록 / 공통 테이블, 백엔드 배포 | 1, 4 |
| 설아 | 홈·내 약·처방 조회, 내 정보·건강 프로필 구현(명세는 4장), 전체 리뷰 / 프론트 배포 | 5 |
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
| 형식 | 요청·응답 모두 JSON. 필드 이름은 snake_case이며 ERD 컬럼 이름과 같게 씁니다. 단, Path와 응답의 기본키는 `id` 대신 `{대상}_id`로 씁니다(예: `intake_id`, `prescription_id`). 예외: 처방 입력(`POST /scans/{scan_id}/confirm`, `POST /prescriptions`)은 6장 모양(AI 문서 4-3 이름)을 쓰고 `create_prescription()`에서 ERD 이름으로 바꿔 저장합니다(4장 매핑표) |
| 성공 응답 | 데이터를 바로 내려주고 `success`, `data` 등으로 감싸지 않습니다 |
| 날짜·시각 | 한국 시간(KST). 날짜 `2026-11-20`, 시각 `18:30`, 일시 `2026-11-20T18:30:00+09:00` |
| 목록 | `?page=1&size=20` → `{"items": [...], "page": 1, "size": 20, "total": 57}`. 예외: 자동완성 검색(`GET /drugs`)은 `{"items": [...]}`만 돌려줍니다 |
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
| `VALIDATION_ERROR` | 422 | 입력값 오류. 대표 `message`는 "입력한 내용을 확인해 주세요"이고, 항목별 사유는 `fields`에 `{ "필드 경로": "사유 문장" }` 형식으로 담습니다(아래 예시) |
| `RATE_LIMITED` | 429 | 호출 제한 초과(OCR·가이드·챗봇) |
| `EXTERNAL_API_ERROR` | 502 | CLOVA OCR·LLM·공공데이터 호출 실패 |
| `INTERNAL_ERROR` | 500 | 그 외 서버 오류 |

`VALIDATION_ERROR` 예시입니다. 요청 모양이 틀린 경우(필수 칸 없음, 글자 수, 형식)는 서버 공용 핸들러가 이 모양으로 바꿔 내려줍니다(`app/core/exceptions.py`, #50).

```json
{
  "code": "VALIDATION_ERROR",
  "message": "입력한 내용을 확인해 주세요",
  "fields": {
    "birth_date": "필수 항목이에요",
    "drugs[0].dose_per_time": "형식이 맞지 않아요"
  }
}
```

- 필드 경로: 요청 본문 기준 칸 이름을 점으로 잇고, 목록 순번은 대괄호로 씁니다(예: `drugs[1].dosage.doses[0].timing`). 순번은 보낸 목록의 순서(0부터)입니다.
- 사유 문장: 서버가 한국어로 보내고 프론트는 그대로 띄웁니다. 한 칸에 사유가 여러 개면 첫 번째만 보냅니다.
- 에러 코드는 서버 코드에서 `ErrorCode` Enum으로 씁니다(글자로 직접 쓰지 않음).

영역별 에러 코드는 각 섹션에서 추가합니다(예: `DOCUMENT_EXPIRED`).

### 1-2. 오래 걸리는 작업 (OCR · 가이드 생성)

1. 요청 API는 작업을 시작하고 바로 `202 Accepted`와 대상 ID를 돌려줍니다.
2. 프론트는 상태 조회 API를 2초 간격으로 호출합니다.
3. 상태 값은 ERD enum(`document_status`, `guide_status`)을 그대로 씁니다.
4. 최대 대기 시간과 실패 시 화면 문구는 각 API 명세에 적습니다.

### 1-3. 챗봇 답변 (스트리밍)

SSE(`text/event-stream`)로 내려줍니다. 이벤트 이름과 `data`는 백엔드 합의(전달사항 2-4)에 따라 **7-6을 기준**으로 하고, 아래는 요약입니다. 바꿀 때는 7-6을 먼저 고칩니다.

| 순서 | event | 보내는 쪽 | 언제 | data |
| --- | --- | --- | --- | --- |
| 0 | `meta` | API | 질문을 저장한 직후 | `{"user_message_id": 811, "masked_content": "..."}` |
| 1 | `emergency` | AI | 응급 표현이 있을 때, LLM보다 먼저 | `{"type": "physical" 또는 "self_harm", "call": "119" 또는 "109", "text": "..."}`. `self_harm`이면 바로 `done` |
| 1' | `out_of_scope` | AI | 답할 수 없는 질문 | `{"type": "diagnosis" / "prescription_change" / "unrelated", "text": "..."}` → 바로 `done` |
| 2 | `delta` | AI | 답변 글자 조각(여러 번) | `{"text": "지금 드시는"}` |
| 3 | `sources` | AI | 답변이 끝났을 때 | `{"items": [{"drug_id": 1204, "name": "..."}]}`. 약 근거는 `drug_id`, 생활습관·질환 자료 근거는 `rag_document_id` (7-1 비고) |
| 4 | `done` | API | 마지막 | `{"message_id": 812, "show_profile_link": false}` |
| - | `error` | AI | 도중에 실패 | `{"code": "EXTERNAL_API_ERROR", "message": "답변을 불러오지 못했어요. 다시 보내기를 눌러 주세요"}`. 사용량 차감 규칙은 2차(CHAT-006) |

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

경로 앞의 `/api/v1`은 생략했습니다. AI 파트가 먼저 정리한 API는 AI 파트 기획 문서 6장의 이름을 그대로 가져왔습니다. 합계 28개 + 내부 함수 4개입니다(민정 7+내부 1 · 채민 8+내부 1 · 유정 6+내부 1 · 설아 7+내부 1). `GET /users/me`, `GET·PUT /users/me/health-profile`은 명세는 4장(민정), 구현은 설아입니다(11/23).

| 영역 | 메서드 | 경로 | 설명 | 요구사항 | 화면 | 담당 | 상태 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 인증 | POST | `/auth/kakao` | 카카오 인가 코드로 로그인·가입, 토큰 발급 | USER-002 | A-1 | 민정 | 리뷰 요청 |
| 인증 | POST | `/auth/refresh` | 토큰 재발급 | USER-006 | - | 민정 | 리뷰 요청 |
| 인증 | POST | `/auth/logout` | 로그아웃(리프레시 토큰 무효화) | USER-006 | 공통 헤더 | 민정 | 리뷰 요청 |
| 회원 | GET | `/users/me` | 내 정보 | USER-008 | E-1 | 설아(명세 4장) | 확정 |
| 회원 | POST | `/users/me/profile` | 추가 정보 입력 + 필수 약관 동의 | USER-002 | A-1 | 민정 | 리뷰 요청 |
| 회원 | GET | `/users/me/health-profile` | 건강 프로필 조회 | USER-010 | E-2 | 설아(명세 4장) | 확정 |
| 회원 | PUT | `/users/me/health-profile` | 건강 프로필 저장(기저질환 포함) | USER-010 | E-2 | 설아(명세 4장) | 확정 |
| 복약 | GET | `/intakes?date=` | 날짜별 복용 기록(최근 3일) | MED-005 | A-2 | 민정 | 리뷰 요청 |
| 복약 | PATCH | `/intakes/{intake_id}` | 복용 체크·취소 + 꽃 결과 | MED-005·017 | A-2 | 민정 | 리뷰 요청 |
| 처방 | POST | `/prescriptions` | 처방 직접 입력(약 검색 + 숫자 입력 + 복용 조건 선택) → `create_prescription()` | MED-001 | B-1(직접 입력) | 민정 | 리뷰 요청 |
| 홈 | GET | `/home?date=` | 날짜별 원형 약통 화면 데이터 한 번에(`GET /intakes` 값 + 요일 미니 약통·다음 복용·가이드 안내) | MED-005·008·009·016·017 | A-2 | 설아 | 리뷰 요청 |
| 내 약 | GET | `/prescription-items/{prescription_item_id}` | 약 상세: 내 복용 정보 + 공공데이터(매칭 안 된 약은 `null`) | MED-002, OCR-005 | C-2 | 설아 | 리뷰 요청 |
| 처방 | GET | `/prescriptions` | 처방 목록(복용 중 / 종료) | MED-002 | C-1 | 설아 | 리뷰 요청 |
| 처방 | GET | `/prescriptions/{prescription_id}` | 처방 상세(약·복용 조건·시간표) | MED-002 | C-1 | 설아 | 리뷰 요청 |
| 처방 등록 | POST | `/scans` | 처방전·약봉투 파일 업로드 → 읽기 시작(202) | OCR-001·002 | B-1 | 채민 | 리뷰 요청 |
| 처방 등록 | GET | `/scans/{scan_id}` | 진행 상태 또는 인식 결과 | OCR-002·003·004 | B-1, B-2 | 채민 | 리뷰 요청 |
| 처방 등록 | PATCH | `/scans/{scan_id}` | 인식 결과 수정·문서 종류 다시 고르기 | OCR-001·004 | B-2 | 채민 | 리뷰 요청 |
| 처방 등록 | GET | `/scans/{scan_id}/pages/{page_no}/image` | 원본 페이지 이미지 | OCR-004 | B-2 | 채민 | 리뷰 요청 |
| 처방 등록 | POST | `/scans/{scan_id}/confirm` | 확정 → `create_prescription()` 호출 → 원본 삭제 | OCR-004 | B-2 | 채민 | 리뷰 요청 |
| 처방 등록 | DELETE | `/scans/{scan_id}` | 읽는 중 취소 → 작업 중단·원본 바로 삭제 | OCR-002, NFR-004 | B-1, B-2 | 채민 | 리뷰 요청 |
| 약 정보 | GET | `/drugs?q=&limit=` | 약 검색(OCR 매칭 후보는 `limit=3`, 직접 입력 검색은 기본 10) | OCR-005, MED-001 | B-2, B-1(직접 입력) | 채민 | 리뷰 요청 |
| 처방 등록 | PATCH | `/dose-conditions/{condition_id}` | '복용 조건 확인 필요' 항목을 회원이 고름 | MED-008 | B-2 | 채민 | 리뷰 요청 |
| 가이드 | GET | `/prescriptions/{prescription_id}/guides` | 복약·생활습관 가이드 보기(만드는 중이면 진행 상태) | GUIDE-001·002·004·006·007 | D-2, C-1 | 유정 | 리뷰 요청 |
| 가이드 | POST | `/prescriptions/{prescription_id}/guides/retry` | 실패 화면의 [다시 시도] | GUIDE-007 | D-2 | 유정 | 리뷰 요청 |
| 가이드 | GET | `/guides` | 내 가이드 목록 | GUIDE-004 | D-1 | 유정 | 리뷰 요청 |
| 챗봇 | GET | `/chat/suggestions` | 추천 질문 3개 | CHAT-001 | F-1 | 유정 | 리뷰 요청 |
| 챗봇 | POST | `/chat/sessions` | 채팅창을 열 때 새 대화 만들기 | CHAT-001 | F-1 | 유정 | 리뷰 요청 |
| 챗봇 | POST | `/chat/sessions/{session_id}/messages` | 질문 보내기 → 답변(SSE) | CHAT-001·002·004·005, VERI-004 | F-1 | 유정 | 리뷰 요청 |
| 내부 | - | `verify_guide()` | 가이드 검증(원문 대조·빠진 약·금지 표현) | VERI-001·002·004 | - | 채민 | 리뷰 요청 |
| 내부 | - | `start_guide_generation()` | 처방 확정 후 가이드 생성 시작(비동기) | GUIDE-001·002 | - | 유정 | 리뷰 요청 |
| 내부 | - | `get_confirmed_prescription()` | 확정 처방 + 회차별 복용 조건 조회 | OCR-004, MED-008 | - | 설아 | 리뷰 요청 |
| 내부 | - | `create_prescription()` | 처방 저장 → 시간표 계산 → 복용 기록 생성 → 가이드 생성 시작(OCR 확정·직접 입력 공용) | OCR-004, MED-001·009 | - | 민정 | 리뷰 요청 |

---

### 3-1. API가 아닌 작업 분담

API 개수만으로는 보이지 않는 작업을 함께 나눕니다.

| 작업 | 담당 | 내용 |
| --- | --- | --- |
| 공통 규칙·인증 미들웨어 | 민정 | 1번 공통 규칙 확정, JWT 인증·`PROFILE_REQUIRED` 처리 |
| 공통 테이블 | 민정 | `users`, `prescriptions`, `prescription_items`, `dose_conditions`처럼 여러 사람이 쓰는 테이블의 모델·마이그레이션을 먼저 올립니다. 나머지 테이블은 각자 자기 API가 쓰는 테이블을 만듭니다 |
| 처방 저장 함수 | 민정 | `create_prescription()` 하나로 처방·약·복용 조건 저장, 기본 일과로 `dose_schedules` 계산, `intake_logs` 생성, `start_guide_generation()` 호출까지 한 번에 처리합니다. OCR 확정과 직접 입력이 모두 이 함수를 부르므로 저장 로직이 두 벌로 갈라지지 않습니다 |
| 공공데이터 `drugs` 적재 | 유정 | RAG용 e약은요 데이터를 받을 때 `drugs` 테이블에도 함께 넣습니다. 같은 데이터를 두 번 받지 않도록 한 파이프라인으로 처리합니다 |
| 개인정보 가리기 함수 | 채민 | `mask_text()`: OCR 결과·챗봇 질문을 저장하거나 LLM에 보내기 전에 이름·주민등록번호·환자번호·면허번호·연락처를 가립니다(NFR-004). OCR(6장)과 챗봇(7-6)이 같은 함수를 씁니다 |
| 백엔드 배포 | 민정 | EC2 + Docker Compose (NFR-007). 서버 주소는 `https://api.daol.site`(11/23 도메인 구매): EC2에 Elastic IP를 붙이고, Nginx에 Let's Encrypt 인증서를 붙입니다(DNS `api` A 레코드는 설아). 프론트가 Vercel rewrites로 `/api/*`를 넘겨받는 구조라 CORS credentials 설정은 하지 않습니다(4-1) |
| 프론트 배포 | 설아 | Vercel. `vercel.json` rewrites로 `/api/:path*`를 `https://api.daol.site/api/:path*`로 넘겨 같은 주소처럼 씁니다(4-1). 로컬 개발도 개발 서버 프록시로 같은 방식을 씁니다. 첫 배포 때 30MB 업로드·챗봇 SSE가 프록시를 통과하는지 테스트하고, 막히면 4-1 Plan B로 바꿉니다 |

---

<!-- 민정 START · 인증·회원 -->
## 4. 인증·회원 / 복용 기록 / 처방 직접 입력

담당: 민정 · 관련 화면: A-1, A-2, B-1(직접 입력), E-1, E-2 · 관련 테이블: `users`, `user_consents`, `refresh_tokens`, `health_profiles`, `user_conditions`, `intake_logs`, `daily_flowers`, `prescriptions`, `prescription_items`, `dose_conditions`, `dose_schedules` · 내부 함수: `create_prescription()`

> 1-4 양식으로 작성했습니다. 필드 이름과 enum 값은 PR된 1차 ERD(`daol_erd_phase1.dbml`, 테이블 20개)에 맞췄습니다. 처방 입력은 6장 확정 API와 같은 모양을 쓰고 `create_prescription()`에서 ERD 이름으로 바꿔 저장합니다. 6·7장에서 민정에게 온 질문의 답과 ERD 수정 제안은 4-8·4-9에 모았습니다.

### 4-0. 이 섹션에서 추가하는 에러 코드

| code | HTTP | 언제 | 화면 처리 |
| --- | --- | --- | --- |
| `KAKAO_AUTH_FAILED` | 401 | 인가 코드가 잘못됐거나 만료됨, 카카오 사용자 정보를 받지 못함 | "카카오 로그인에 실패했어요. 다시 시도해 주세요" → 로그인 페이지 |
| `REJOIN_RESTRICTED` | 403 | 탈퇴한 지 30일이 지나지 않은 카카오 계정 | `message`를 그대로 표시 |
| `REFRESH_TOKEN_EXPIRED` | 401 | 리프레시 토큰이 없음·만료·무효화됨 | "로그인이 만료되었습니다" → 로그인 페이지. 재발급을 다시 시도하지 않습니다 |
| `PROFILE_ALREADY_COMPLETED` | 409 | 추가 정보를 이미 입력한 회원이 다시 호출 | `GET /users/me`를 다시 불러 홈으로 이동 |
| `INTAKE_EDIT_EXPIRED` | 422 | 수정 가능 기간(오늘−3일 ~ 오늘)보다 이전 기록 | "3일이 지난 기록은 수정할 수 없어요" |
| `INTAKE_FUTURE_DATE` | 422 | 내일 이후 날짜의 기록을 체크 | "아직 오지 않은 날은 체크할 수 없어요" |
| `DRUG_NOT_FOUND` | 422 | 직접 입력에서 `drugs`에 없는 `drug_id`를 보냄 | "약을 다시 검색해서 골라 주세요" |
| `PRESCRIPTION_ALREADY_ENDED` | 422 | 시작일과 총 일수로 계산한 종료일이 오늘보다 이전 | "이미 복용이 끝난 처방이에요. 시작일을 확인해 주세요" |

`REJOIN_RESTRICTED`는 1-1 형식에 날짜 하나를 더해서 내려줍니다.

```json
{ "code": "REJOIN_RESTRICTED", "message": "탈퇴 후 30일 동안은 다시 가입할 수 없어요. 12월 15일부터 가입할 수 있어요", "rejoin_available_date": "2026-12-15" }
```

`VALIDATION_ERROR`의 `fields`는 1-1에 적은 `{ "필드 경로": "사유 문장" }` 형식을 따릅니다.

```json
{ "code": "VALIDATION_ERROR", "message": "입력한 내용을 확인해 주세요", "fields": { "items[0].total_days": "1~365일 사이로 입력해 주세요" } }
```

### 4-1. 리프레시 토큰 전달 방식

요구사항(REQ-USER-006 비고, REQ-NFR-003)대로 리프레시 토큰은 HttpOnly 쿠키로 주고받습니다. 액세스 토큰만 응답 본문에 담습니다.

| 항목 | 값 |
| --- | --- |
| 쿠키 | `refresh_token=...; HttpOnly; Secure; SameSite=Lax; Path=/api/v1/auth; Max-Age=1209600`(14일). `Domain`은 넣지 않습니다(호스트 전용 쿠키). 브라우저는 HTTPS인 Vercel 주소와 통신하고, Vercel → EC2 구간도 `https://api.daol.site`로 HTTPS입니다(REQ-NFR-003, 11/23 도메인 구매) |
| 액세스 토큰 | 응답 본문 `access_token`. 프론트는 메모리에만 보관하고 localStorage에 저장하지 않습니다 |
| 서버 저장 | `refresh_tokens.token_hash`(SHA-256), `expires_at`(14일), `revoked_at`(무효화 시각) |
| 배포 구조 | 프론트(Vercel)가 `/api/*` 요청을 rewrites로 EC2에 넘깁니다. 브라우저에는 같은 주소로 보여서 쿠키가 퍼스트파티가 되므로 `SameSite=Lax`로 충분하고, CORS `allow_credentials`·`credentials: "include"` 설정이 필요 없습니다. 프론트는 API를 상대 경로(`/api/v1/...`)로 부릅니다. `SameSite=None` 교차 사이트 쿠키는 사파리가 기본으로 막고 크롬도 막는 쪽이라 쓰지 않습니다(설아님 제안, 11/23) |
| 대안(Plan B) | 첫 배포 때 30MB 업로드(6장)와 챗봇 SSE(7-6)가 프록시를 통과하지 못하면 프록시를 거치지 않고 화면 `daol.site`(Vercel), 서버 `api.daol.site`(EC2 + HTTPS, 이미 준비됨)로 바로 부릅니다. 두 주소는 같은 사이트라 `SameSite=Lax`는 유지되지만 출처(origin)가 달라서 백엔드 CORS `allow_credentials=True` + 허용 Origin 명시 + 프론트 `credentials: "include"`가 다시 필요합니다. 카카오 개발자 콘솔의 Redirect URI도 새 도메인으로 바꿉니다 |

### [POST] /api/v1/auth/kakao
- 설명: 카카오 인가 코드로 로그인합니다. 처음 온 카카오 계정이면 회원을 만든 뒤 로그인합니다.
- 인증: 불필요
- 관련 요구사항: REQ-USER-002, REQ-NFR-003
- 관련 화면: A-1 로그인
- 관련 테이블: `users`, `refresh_tokens`
- Path / Query: 없음
- Request Body:

  ```json
  { "code": "카카오가 redirect_uri로 넘겨준 인가 코드" }
  ```
  `redirect_uri`는 받지 않고 서버 환경 변수(`KAKAO_REDIRECT_URI`)를 씁니다. 카카오 개발자 콘솔에 등록한 값과 같아야 합니다.
- Response Body (200):

  ```json
  {
    "access_token": "eyJhbGciOiJIUzI1NiIs...",
    "token_type": "Bearer",
    "expires_in": 1800,
    "is_new_user": true,
    "is_profile_completed": false,
    "user": { "user_id": 17, "nickname": "다올이a3f9" }
  }
  ```
  응답 헤더 `Set-Cookie`로 리프레시 토큰을 함께 내려줍니다(4-1).
- 에러: `VALIDATION_ERROR`(422) `code` 없음 / `KAKAO_AUTH_FAILED`(401) 인가 코드 오류 → 로그인 페이지 + 안내 / `REJOIN_RESTRICTED`(403) 탈퇴 30일 이내 → 안내 문구 표시 / `EXTERNAL_API_ERROR`(502) 카카오 서버 응답 없음 → "카카오 로그인에 실패했어요. 다시 시도해 주세요"
- 비고:
  - 처리 순서: 인가 코드 → 카카오 토큰 발급 → 사용자 정보 조회 → `users.kakao_id`로 조회 → 없으면 생성 → JWT 발급
  - 회원 식별은 `kakao_id`(카카오 회원번호)만 씁니다. 이메일은 회원이 동의한 경우에만 `users.email`에 저장하고, 없으면 `null`입니다.
  - 닉네임(`users.nickname`, 2~10자, unique)이 이미 있으면 뒤에 무작위 4자리(영문 소문자·숫자)를 붙입니다. 붙인 결과가 10자를 넘으면 카카오 닉네임 앞부분을 6자로 자르고 붙입니다. 카카오 닉네임이 1자면 무작위 4자리를 붙여 2자 이상으로 만듭니다.
  - 카카오 동의 화면에서 취소하면 카카오가 `error=access_denied`로 돌려보냅니다. 이때 프론트는 이 API를 부르지 않고 "카카오 로그인이 취소되었어요"를 보여줍니다.
  - 탈퇴 판정: `users.status = withdrawn`이고 `withdrawn_at` + 30일이 지나지 않았으면 `REJOIN_RESTRICTED`입니다. 30일 뒤에는 행이 영구 삭제되므로 같은 카카오 계정이 새 회원으로 가입됩니다. 탈퇴 기능(REQ-USER-011)은 2차지만 이 판정은 1차에 둡니다.
  - 1차 ERD에는 프로필 이미지 칸, `talk_message` 동의 값, 카카오 토큰 칸이 없어서 셋 다 저장하지 않습니다(4-8). 1차 카카오 동의 항목에서는 `talk_message`를 뺍니다(11/23 결정, 4-8 E4). 카카오톡 알림(REQ-NOTI-005, 2차)을 붙일 때 알림 설정에서 추가 동의를 받습니다.
  - 파트너 간단 가입(3차)은 `signup_type`이 생길 때 이 API에 추가합니다.

### [POST] /api/v1/auth/refresh
- 설명: 쿠키의 리프레시 토큰으로 새 액세스 토큰을 발급합니다. 리프레시 토큰도 새것으로 바꿉니다(회전).
- 인증: 불필요(쿠키 `refresh_token` 필요)
- 관련 요구사항: REQ-USER-006, REQ-NFR-003
- 관련 화면: - (API가 `UNAUTHORIZED`를 돌려주면 프론트가 자동 호출)
- 관련 테이블: `refresh_tokens`, `users`
- Path / Query: 없음
- Request Body: 없음
- Response Body (200):

  ```json
  { "access_token": "eyJhbGciOiJIUzI1NiIs...", "token_type": "Bearer", "expires_in": 1800 }
  ```
  새 리프레시 토큰은 `Set-Cookie`로 내려주고, `expires_at`은 새로 발급한 시점부터 14일입니다.
- 에러: `REFRESH_TOKEN_EXPIRED`(401) 쿠키 없음·만료·무효화·탈퇴 회원 → "로그인이 만료되었습니다" 후 로그인 페이지
- 비고:
  - 쓴 리프레시 토큰은 바로 `revoked_at`을 채웁니다. 이미 무효화된 토큰이 다시 들어오면 탈취로 보고 그 회원의 리프레시 토큰을 모두 무효화합니다.
  - 프론트 흐름: `UNAUTHORIZED`(401) → 재발급 1회 → 성공하면 원래 요청을 다시 보냅니다. 여러 요청이 동시에 401을 받으면 재발급은 한 번만 부르고 나머지는 그 결과를 기다리게 해 주세요. 회전 방식이라 두 번 부르면 두 번째가 실패합니다. 프론트가 재발급 요청을 하나로 묶어(single-flight) 처리합니다(설아님 확인, 11/23)
  - 재발급이 `REFRESH_TOKEN_EXPIRED`이면 다시 재발급하지 않습니다(무한 반복 방지).
  - 재발급할 때마다 만료일도 새로 14일로 잡습니다. 매일 여는 복약 앱이라, 14일 안에 한 번이라도 열면 로그인이 계속 유지됩니다(11/26 설아님 리뷰).
  - `users.status = withdrawn`인 회원은 `REFRESH_TOKEN_EXPIRED`입니다.

### [POST] /api/v1/auth/logout
- 설명: 이 기기의 리프레시 토큰을 무효화하고 쿠키를 지웁니다.
- 인증: 필요
- 관련 요구사항: REQ-USER-006
- 관련 화면: 공통 헤더(로그아웃 버튼)
- 관련 테이블: `refresh_tokens`
- Path / Query: 없음
- Request Body: 없음
- Response Body (204): 본문 없음. `Set-Cookie: refresh_token=; Max-Age=0; Path=/api/v1/auth; HttpOnly; Secure; SameSite=Lax`로 쿠키를 지웁니다.
- 에러: `UNAUTHORIZED`(401) → 재발급 후 다시 시도, 재발급도 실패하면 이미 로그아웃된 것으로 보고 메인 페이지로
- 비고:
  - 쿠키가 없거나 이미 무효화된 토큰이어도 204를 돌려줍니다. 여러 번 눌러도 결과가 같습니다.
  - 이 기기의 토큰 행만 `revoked_at`을 채우고, 다른 기기의 로그인은 유지됩니다.
  - 액세스 토큰은 블랙리스트를 두지 않아 만료(30분)까지 유효합니다. 프론트는 메모리의 액세스 토큰을 지우고 메인 페이지로 이동합니다.

### [GET] /api/v1/users/me
- 설명: 로그인한 회원의 정보입니다. 앱을 처음 열 때 추가 정보 입력 화면으로 보낼지 판단하는 데도 씁니다.
- 인증: 필요(`PROFILE_REQUIRED` 예외 API)
- 관련 요구사항: REQ-USER-008, REQ-USER-002
- 관련 화면: E-1 내 정보, 앱 시작 시 라우팅(프론트가 앱 시작 때 이 API로 추가 정보 입력 화면 / 홈을 고릅니다)
- 관련 테이블: `users`
- Path / Query: 없음
- Request Body: 없음
- Response Body (200):

  ```json
  {
    "user_id": 17,
    "nickname": "다올이a3f9",
    "email": "daol@example.com",
    "name": "김다올",
    "birth_date": "1958-03-14",
    "gender": "female",
    "is_profile_completed": true,
    "created_at": "2026-11-20T10:12:00+09:00"
  }
  ```
  추가 정보 입력 전이면 `name`, `birth_date`, `gender`가 `null`이고 `is_profile_completed`가 `false`입니다.
- 에러: `UNAUTHORIZED`(401) → 재발급
- 비고:
  - `is_profile_completed`는 `users.is_profile_completed` 값입니다. 추가 정보 입력과 필수 약관 3종 동의를 마칠 때 `true`가 됩니다.
  - `users.gender`는 enum이 없는 `varchar(10)`이라 값을 이 문서에서 `male / female`로 정합니다. ERD에 enum 추가를 제안합니다(4-8).
  - 내 정보 화면(REQ-USER-008)은 2차지만, 라우팅에 필요해서 API는 1차에 만듭니다.

### [POST] /api/v1/users/me/profile
- 설명: 최초 로그인 직후 추가 정보(이름·생년월일·성별)와 필수 약관 동의를 받습니다. 성공하면 서비스 화면으로 들어갈 수 있습니다.
- 인증: 필요(`PROFILE_REQUIRED` 예외 API)
- 관련 요구사항: REQ-USER-002, REQ-NFR-004
- 관련 화면: A-1 추가 정보 입력
- 관련 테이블: `users`, `user_consents`
- Path / Query: 없음
- Request Body:

  ```json
  {
    "name": "김다올",
    "birth_date": "1958-03-14",
    "gender": "female",
    "consents": [
      { "consent_type": "terms", "agreed": true },
      { "consent_type": "privacy", "agreed": true },
      { "consent_type": "sensitive_health", "agreed": true }
    ]
  }
  ```

  | 필드 | 규칙 |
  | --- | --- |
  | `name` | 필수, 앞뒤 공백 제거 후 1~20자 |
  | `birth_date` | 필수, `YYYY-MM-DD`, 1900-01-01 ~ 오늘. 만 14세 미만이면 `VALIDATION_ERROR`(`fields.birth_date`: "만 14세 이상만 가입할 수 있어요") |
  | `gender` | 필수, `male / female` |
  | `consents` | `consent_type` 3종(`terms` 이용약관 / `privacy` 개인정보 수집·이용 / `sensitive_health` 민감정보(건강정보) 수집·이용)이 모두 `agreed: true`여야 합니다 |
- Response Body (200): `GET /users/me`와 같은 형식이며 `is_profile_completed`가 `true`입니다.
- 에러: `VALIDATION_ERROR`(422) 입력값 오류·필수 동의 누락 → `fields` 항목 아래에 사유 표시 / `PROFILE_ALREADY_COMPLETED`(409) → 홈으로 이동
- 비고:
  - `users`의 이름·생년월일·성별 저장, `user_consents` 3행 저장, `users.is_profile_completed = true`를 한 트랜잭션으로 처리합니다. `user_consents`는 (회원, 동의 종류)가 unique라 동의 종류마다 한 행입니다.
  - 이름·생년월일·성별은 이후 수정할 수 없으므로(REQ-USER-009) 두 번째 호출은 409로 막습니다.
  - 동의 일시는 `user_consents.agreed_at`(서버 시각)입니다. 약관 버전을 저장할 칸은 ERD에 없습니다(4-8).
  - 만 14세 미만은 법정대리인 동의가 필요해서 1차는 가입을 막습니다(4-9 13). 나이는 KST 오늘 날짜와 `birth_date`로 계산합니다.

### [GET] /api/v1/users/me/health-profile
- 설명: 건강 프로필을 조회합니다. 아직 입력하지 않았으면 404가 아니라 `is_registered: false`와 빈 값을 돌려줍니다. 404는 '없거나 다른 회원의 데이터'라는 뜻으로만 씁니다.
- 인증: 필요
- 관련 요구사항: REQ-USER-010
- 관련 화면: E-2 건강 프로필, '건강 프로필 입력' 팝업 판단(처방 저장 API를 부르기 전에 띄움, 11/23 설아님 동의)
- 관련 테이블: `health_profiles`, `user_conditions`
- Path / Query: 없음
- Request Body: 없음
- Response Body (200):

  ```json
  {
    "is_registered": true,
    "height_cm": 162.5,
    "weight_kg": 58.0,
    "conditions": [
      { "condition_code": "hypertension", "condition_text": null },
      { "condition_code": "other", "condition_text": "갑상선 질환" }
    ],
    "allergies": "페니실린, 땅콩",
    "is_pregnant_or_nursing": null,
    "is_smoker": false,
    "drinks_per_week": 1,
    "exercise_per_week": 3,
    "updated_at": "2026-11-20T11:03:00+09:00"
  }
  ```
  입력 전(`health_profiles` 행 없음)이면 `is_registered: false`, `conditions: []`, 나머지 값은 모두 `null`입니다.
- 에러: `UNAUTHORIZED`(401) → 재발급
- 비고:
  - `is_registered`는 `health_profiles` 행이 있는지입니다(ERD: 행이 없으면 가이드 생성 전 입력 유도 팝업).
  - `condition_code` 값(ERD `user_conditions`): `hypertension`(고혈압) / `diabetes`(당뇨) / `dyslipidemia`(이상지질혈증) / `heart`(심장질환) / `kidney`(신장질환) / `liver`(간질환) / `other`(기타, `condition_text`에 직접 입력). 한글 이름은 프론트가 가집니다.
  - '없음'은 ERD대로 `user_conditions` 행이 없는 것으로 표현합니다. `is_registered: true`인데 `conditions: []`이면 '없음'을 고른 것입니다.
  - 가이드·챗봇 개인화 입력이라 이 값을 프롬프트에서 그대로 쓰는지 유정님과 확인합니다.

### [PUT] /api/v1/users/me/health-profile
- 설명: 건강 프로필을 저장합니다. 처음 등록과 수정에 같이 쓰며, 보낸 내용으로 전체를 바꿉니다.
- 인증: 필요
- 관련 요구사항: REQ-USER-010, REQ-NFR-004
- 관련 화면: E-2 건강 프로필
- 관련 테이블: `health_profiles`, `user_conditions`
- Path / Query: 없음
- Request Body:

  ```json
  {
    "height_cm": 162.5,
    "weight_kg": 58.0,
    "conditions": [
      { "condition_code": "hypertension" },
      { "condition_code": "other", "condition_text": "갑상선 질환" }
    ],
    "allergies": "페니실린, 땅콩",
    "is_pregnant_or_nursing": null,
    "is_smoker": false,
    "drinks_per_week": 1,
    "exercise_per_week": 3
  }
  ```

  | 필드 | 규칙 |
  | --- | --- |
  | `height_cm` | 50.0~250.0, 소수 첫째 자리까지, `null` 가능 |
  | `weight_kg` | 10.0~300.0, 소수 첫째 자리까지, `null` 가능 |
  | `conditions` | 0개 이상. '없음'은 빈 배열. `other`는 `condition_text` 1~200자 필수, 최대 5개. `other`를 뺀 같은 코드는 중복 불가 |
  | `allergies` | 0~200자, `null` 가능 |
  | `is_pregnant_or_nursing` | 회원 `gender`가 `female`일 때만 `true / false`. 그 외에는 `null`만 허용 |
  | `is_smoker` | `true / false / null` |
  | `drinks_per_week`, `exercise_per_week` | 0~7 정수, `null` 가능 |

  모든 항목을 비워 둘 수 있습니다(입력 최소화, REQ-NFR-016).
- Response Body (200): `GET /users/me/health-profile`과 같은 형식이며 `is_registered`가 `true`입니다.
- 에러: `VALIDATION_ERROR`(422) → `fields` 항목 아래에 사유 표시
- 비고:
  - ERD에서 암호화 칸은 `health_profiles.allergies`와 `user_conditions.condition_text`입니다(AES-256, REQ-NFR-004). 키·몸무게 등 숫자 칸은 평문입니다.
  - `health_profiles` upsert와 `user_conditions` 삭제 후 다시 넣기를 한 트랜잭션으로 처리합니다.
  - 이미 만든 가이드는 다시 만들지 않고, 다음에 만드는 가이드부터 반영됩니다(재생성은 REQ-GUIDE-005, 2차) → 유정님 확인

### [GET] /api/v1/intakes?date=
- 설명: 하루치 복용 기록을 복용 시각 순으로 돌려줍니다. 홈 아래 체크리스트 목록과 지난 날짜 확인·수정에 씁니다.
- 인증: 필요
- 관련 요구사항: REQ-MED-005, REQ-MED-016
- 관련 화면: A-2 홈(체크리스트, 요일 미니 약통에서 지난 날짜를 눌렀을 때)
- 관련 테이블: `intake_logs`, `prescription_items`, `dose_conditions`, `dose_schedules`, `drugs`, `daily_flowers`
- Path / Query: Query `date`(`YYYY-MM-DD`, 생략하면 오늘(KST)). 조회는 오늘−6일 ~ 오늘(요일 미니 약통 7일), 수정은 오늘−3일 ~ 오늘
- Request Body: 없음
- Response Body (200):

  ```json
  {
    "log_date": "2026-11-20",
    "is_editable": true,
    "uses_default_routine": true,
    "slots": [
      {
        "scheduled_time": "08:30",
        "items": [
          { "intake_id": 3019, "prescription_id": 512, "prescription_item_id": 1301, "drug_name": "다올정 10mg", "dose_text": "1정", "condition_label": "아침 식후 30분", "status": "taken", "taken_at": "2026-11-20T08:41:05+09:00" }
        ]
      },
      {
        "scheduled_time": "13:00",
        "items": [
          { "intake_id": 3020, "prescription_id": 512, "prescription_item_id": 1301, "drug_name": "다올정 10mg", "dose_text": "1정", "condition_label": "점심 식후 30분", "status": "taken", "taken_at": "2026-11-20T13:12:40+09:00" }
        ]
      },
      {
        "scheduled_time": "19:00",
        "items": [
          { "intake_id": 3021, "prescription_id": 512, "prescription_item_id": 1301, "drug_name": "다올정 10mg", "dose_text": "1정", "condition_label": "저녁 식후 30분", "status": "pending", "taken_at": null }
        ]
      },
      {
        "scheduled_time": "23:00",
        "items": [
          { "intake_id": 3022, "prescription_id": 512, "prescription_item_id": 1302, "drug_name": "새싹캡슐", "dose_text": "1캡슐", "condition_label": "취침 전", "status": "pending", "taken_at": null }
        ]
      }
    ],
    "as_needed_items": [
      { "prescription_item_id": 1303, "drug_name": "햇살정", "dose_text": "1정", "condition_summary": "필요시 (하루 최대 3회)" }
    ],
    "schedule_check_items": [
      {
        "prescription_id": 512,
        "prescription_item_id": 1304,
        "drug_name": "물방울정",
        "dose_text": "1정",
        "condition_summary": "1일 2회 식후 30분",
        "schedule_status": "needs_check",
        "reason": "meal_unknown",
        "conditions": [
          { "condition_id": 5014, "dose_no": 1, "reason": "meal_unknown", "timing": "after_meal", "offset_min": 30 },
          { "condition_id": 5015, "dose_no": 2, "reason": "meal_unknown", "timing": "after_meal", "offset_min": 30 }
        ]
      },
      {
        "prescription_id": 512,
        "prescription_item_id": 1305,
        "drug_name": "구름정",
        "dose_text": "1정",
        "condition_summary": "복용 조건 확인 필요",
        "schedule_status": "needs_check",
        "reason": "timing_unknown"
      }
    ],
    "day_summary": { "log_date": "2026-11-20", "done_count": 2, "total_count": 4 },
    "flower": { "bloomed": false }
  }
  ```
- 에러: `VALIDATION_ERROR`(422) 날짜 형식 오류 또는 조회 범위 밖 → 날짜 이동 버튼 비활성화로 미리 막습니다
- 비고:
  - `slots`는 `intake_logs.scheduled_time`(그날 복용 시각 스냅샷)이 같은 기록끼리 묶습니다. 30분 이내 묶음(REQ-MED-009)은 2차이며, 그때 묶는 기준만 바뀝니다.
  - `drug_name`은 표시용 값입니다. `drug_id`가 있으면 `drugs.item_name`, 없으면 `prescription_items.drug_name_raw`입니다. `dose_text`는 `intake_logs.dose_text`(그날 용량 스냅샷)입니다.
  - `log_date`는 ERD상 '기상 ~ 다음 기상 전' 하루지만, 1차는 기본 일과(기상 07:00, 취침 23:00)라 KST 달력 날짜와 같습니다.
  - 지난 날짜의 `pending`은 `missed`로 바꿉니다. 스케줄러 없이 이 API와 PATCH가 불릴 때 오늘 이전 `pending`을 `missed`로 갱신합니다. 2차에 알림 스케줄러가 생기면 자정 작업으로 옮깁니다. `GET /home?date=`(5장)도 같은 함수를 씁니다(설아님 확인, 11/23)
  - 하루치 조회는 공용 서비스 함수 `get_daily_intakes(db, user_id, log_date, *, now=None)`(`app/services/intake_service.py`)가 맡고, `GET /intakes`와 `GET /home?date=`(5장)가 같이 부릅니다. 이 함수가 지난 날짜 `pending` → `missed`를 바꾸므로 커밋은 부른 API가 합니다(두 API 모두 조회지만 커밋함).
  - 필요시 약(`as_needed_items`)은 1차에서 목록만 보여주고 체크하지 않습니다(11/23 확정, 4-9 6). ERD `intake_logs`의 필요시 체크용 칸(`is_as_needed`, `scheduled_time = NULL`)은 2차에 `POST /intakes`를 만들 때 씁니다.
  - `schedule_check_items`는 `dose_schedules.status = needs_check`인 약입니다. 복용 기록이 없습니다. 오늘만 담고(지난 날짜면 빈 배열) 복용 중인 약만 담습니다(5-0 '복용 중' 기준). 약마다 `reason`으로 홈 화면 처리를 나눕니다(11/23 설아님 확인).

    | `reason` | 뜻 | 홈 화면 | 내려주는 칸 |
    | --- | --- | --- | --- |
    | `meal_unknown` | 식전·식후는 읽었지만 끼니를 모름 | 홈에서 바로 끼니를 고름(11/20 설아·채민 결정) | 공통 칸 + `conditions` |
    | `timing_unknown` | 복용법 자체를 못 읽음 | 끼니를 고르지 않고 안내 카드만 보여 줌. "처방 상세에서 확인하기" → 그 약의 약 상세(C-2)에서 회차마다 `PATCH /dose-conditions/{condition_id}`(6장)로 식전·식후·끼니를 고름 | 공통 칸만(`conditions` 없음) |

  - 공통 칸: `prescription_id`, `prescription_item_id`, `drug_name`, `dose_text`, `condition_summary`, `schedule_status`, `reason`
  - 한 약에 두 `reason`이 섞이면(회차 하나라도 `timing_unknown`) 그 약은 `timing_unknown`으로 내려줍니다. 약 상세(C-2)에서 회차마다 다시 고르게 하기 위함입니다.
  - `meal_unknown`의 `conditions`에는 `needs_check`인 회차만 `dose_no` 순으로 담습니다. 회차의 `reason`은 `create_prescription()`의 `ConditionToConfirm.reason`과 같은 값입니다: `dose_conditions.condition_type`이 `NULL`이면 `timing_unknown`, 식전·식후인데 `meal`이 `NULL`이면 `meal_unknown`. `timing`·`offset_min`은 지금 저장된 값입니다.
  - 홈은 `meal_unknown` 회차마다 `PATCH /dose-conditions/{condition_id}`(6장)를 따로 부릅니다. 끼니만 고르고 `timing`·`offset_min`은 받은 값을 그대로 보냅니다.
  - 한 약의 회차를 모두 고르면 `recalculate_schedule()`이 시간표와 복용 기록을 만들어 그 약이 `slots`로 옮겨갑니다. 홈은 PATCH 응답 뒤 `GET /home?date=`(5장)를 다시 불러 화면을 갱신합니다.
  - 문구는 서버가 `dose_conditions`로 만든 표시용 값이고, 프론트는 그대로 보여줍니다. `slots` 안의 `condition_label`은 회차 하나의 문구(`아침 식후 30분`)로 `format_condition_label()`이, `as_needed_items`·`schedule_check_items`의 `condition_summary`는 약 한 줄의 문구(`필요시 (하루 최대 3회)`, `1일 2회 식후 30분`)로 `format_condition_summary()`가 만듭니다. 두 함수는 `app/services/prescription_query.py`에 두고 4·5장이 같이 씁니다(문구 규칙은 5-0, 11/23 민정님 리뷰).

### [PATCH] /api/v1/intakes/{intake_id}
- 설명: 복용 기록을 체크하거나 취소합니다. 그날 복용을 모두 마치면 꽃이 핍니다. (2번 예시를 이어서 확정)
- 인증: 필요
- 관련 요구사항: REQ-MED-005, REQ-MED-016, REQ-MED-017
- 관련 화면: A-2 홈(원형 약통 칸, 체크리스트)
- 관련 테이블: `intake_logs`, `daily_flowers`
- Path / Query: Path `intake_id`(`intake_logs.id`)
- Request Body:

  ```json
  { "status": "taken" }
  ```
  `status`는 `taken`(체크) 또는 `pending`(체크 취소)만 받습니다. `missed`는 서버만 씁니다.
- Response Body (200):

  ```json
  {
    "intake_id": 3021,
    "status": "taken",
    "taken_at": "2026-11-20T18:42:10+09:00",
    "day_summary": { "log_date": "2026-11-20", "done_count": 4, "total_count": 4 },
    "flower": { "bloomed": true, "just_bloomed": true }
  }
  ```
- 에러: `NOT_FOUND`(404) 없는 기록·다른 회원의 기록 → 목록 새로고침 / `INTAKE_EDIT_EXPIRED`(422) 오늘−3일보다 이전 → "3일이 지난 기록은 수정할 수 없어요" / `INTAKE_FUTURE_DATE`(422) 내일 이후 → "아직 오지 않은 날은 체크할 수 없어요" / `VALIDATION_ERROR`(422) `status` 값 오류
- 비고:
  - 오늘 기록을 취소하면 `pending`, 지난 날짜(오늘−1 ~ −3일) 기록을 취소하면 하루가 끝났으므로 `missed`로 저장하고 응답 `status`도 `missed`입니다. 취소하면 `taken_at`은 `null`로 비웁니다.
  - 오늘 기록은 시각 전이어도 체크할 수 있습니다(미리 먹는 경우).
  - 지금과 같은 상태를 다시 보내면 바꾸지 않고 200을 돌려주며 `just_bloomed`는 `false`입니다. 칸을 두 번 눌러도 안전합니다.
  - 꽃: 그날(`log_date`) 회원의 `intake_logs` 중 `is_as_needed = false`인 기록이 모두 `taken`이면 `daily_flowers` 행을 만들고 `just_bloomed: true`, 하나라도 풀리면 그날 행을 지우고 `bloomed: false`입니다.
  - 지난 날짜 수정으로 완료돼도 꽃은 심습니다. 포인트 미지급 규칙(REQ-MED-017 예외)은 포인트가 생기는 3차에 붙입니다.
  - `intake_logs` 갱신과 `daily_flowers` 생성·삭제는 한 트랜잭션으로 처리합니다. ERD의 `daily_flowers (user_id, log_date)` unique 덕분에 동시에 눌러도 꽃이 두 개 생기지 않습니다.
  - `taken_at`은 서버 시각입니다.

### [POST] /api/v1/prescriptions
- 설명: OCR 없이 약을 검색해 처방을 직접 등록합니다. 저장은 `create_prescription()`을 불러 OCR 확정과 같은 경로로 처리합니다.
- 인증: 필요
- 관련 요구사항: REQ-MED-001(1차 축소 범위), REQ-MED-008, REQ-MED-009
- 관련 화면: B-1(직접 입력)
- 관련 테이블: `prescriptions`, `prescription_items`, `dose_conditions`, `dose_schedules`, `intake_logs`, `guides`, `drugs`(조회)
- Path / Query: 없음
- Request Body: 6장 확정 API(`POST /scans/{scan_id}/confirm`)의 Request Body와 같은 모양입니다. `line_no`, `instruction_text`만 없습니다. B-1 직접 입력과 B-2 확인 화면이 같은 약 줄 폼을 쓸 수 있습니다.

  ```json
  {
    "hospital_name": "다올내과의원",
    "prescribed_date": null,
    "memo": null,
    "drugs": [
      {
        "drug_id": 1024,
        "drug_name": "다올정 10mg",
        "dose_per_time": { "text": "1정", "min": 1, "max": 1, "unit": "정", "parsed": true },
        "times_per_day": 3,
        "total_days": 30,
        "dosage": {
          "parsed_by": "user",
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
        "drug_id": 2048,
        "drug_name": "새싹캡슐",
        "dose_per_time": { "text": "1캡슐", "min": 1, "max": 1, "unit": "캡슐", "parsed": true },
        "times_per_day": 1,
        "total_days": 30,
        "dosage": {
          "parsed_by": "user",
          "as_needed": false,
          "doses": [
            { "dose_no": 1, "meal": null, "timing": "bedtime", "offset_min": null }
          ],
          "cycle": { "type": "daily", "start_date": "2026-11-20" }
        }
      },
      {
        "drug_id": null,
        "drug_name": "햇살시럽",
        "dose_per_time": { "text": "5mL", "min": 5, "max": 5, "unit": "mL", "parsed": true },
        "times_per_day": 3,
        "total_days": 5,
        "dosage": {
          "parsed_by": "user",
          "as_needed": true,
          "doses": [],
          "cycle": { "type": "daily", "start_date": "2026-11-20" }
        }
      }
    ]
  }
  ```

  | 필드 | 필수 | 규칙 |
  | --- | --- | --- |
  | `hospital_name` | 선택 | 0~100자. 1차 직접 입력 화면(B-1-3)에는 입력 칸이 없어 보내지 않습니다(병원명·메모 입력은 2차, REQ-MED-001) |
  | `prescribed_date` | 선택 | 직접 입력은 보통 `null` |
  | `memo` | 선택 | 0~500자(직접 입력만). 1차 화면에서는 보내지 않습니다(2차) |
  | `drugs` | 필수 | 1~20개 |
  | `drug_id` | 선택 | `GET /drugs?q=` 검색 결과에서 고른 약. 검색에 없는 약은 `null`로 이름만 저장(6장 `GET /drugs` 안내와 같음). 화면은 "검색 결과가 없어요 → 이름 그대로 저장" 버튼을 OCR과 같게 둡니다(11/23 설아님 확인) |
  | `drug_name` | 필수 | 1~200자. `drug_id`가 있으면 그 약의 `drugs.item_name`으로 저장합니다 |
  | `dose_per_time` | 필수 | 직접 입력은 숫자 하나라 `min = max`(0보다 큰 수, 소수 셋째 자리까지), `unit` 1~10자, `parsed: true`. `text`를 비우면 서버가 `min` + `unit`으로 채웁니다(예: `1정`) |
  | `times_per_day` | 필수 | 1~4. 필요시 약은 하루 최대 횟수 |
  | `total_days` | 필수 | 1~365 |
  | `dosage.parsed_by` | 필수 | 직접 입력은 `user` |
  | `dosage.as_needed` | 필수 | `true`면 `doses`는 빈 배열. 필요시는 약 단위 조건이라 화면에서도 회차별 칩이 아닌 약 단위 '필요 시' 토글로 받습니다(11/23 설아님 확인) |
  | `dosage.doses` | 필수 | `as_needed: false`면 `times_per_day`개, `dose_no`는 1부터 차례로 |
  | `doses[].timing` | 필수 | `after_meal`(식후 n분) / `before_meal`(식전 n분) / `bedtime`(취침 전). 직접 입력은 `null` 불가 |
  | `doses[].meal` | 식전·식후만 | `breakfast / lunch / dinner`. 한 약 안에서 같은 끼니는 한 번만. 취침 전은 `null` |
  | `doses[].offset_min` | 식전·식후만 | 0~120. 취침 전은 `null` |
  | `dosage.cycle` | 필수 | `type`은 1차에 `daily`만. `start_date`(프론트 기본값 오늘)부터 계산한 종료일(시작일 + 총 일수 − 1)이 오늘 이후여야 합니다 |

  직접 입력은 식전·식후마다 끼니를 고르게 해서 '복용 조건 확인 필요'가 생기지 않게 합니다. 1일 3회면 프론트가 아침·점심·저녁을 미리 채워 둡니다.
- Response Body (201):

  ```json
  {
    "prescription_id": 512,
    "source": "manual",
    "status": "active",
    "items": [
      {
        "prescription_item_id": 1301,
        "drug_id": 1024,
        "drug_name": "다올정 10mg",
        "dose_text": "1정",
        "start_date": "2026-11-20",
        "end_date": "2026-12-19",
        "is_as_needed": false,
        "schedule_status": "ok",
        "schedules": [
          { "condition_id": 5001, "dose_no": 1, "dose_time": "08:30", "condition_label": "아침 식후 30분" },
          { "condition_id": 5002, "dose_no": 2, "dose_time": "13:00", "condition_label": "점심 식후 30분" },
          { "condition_id": 5003, "dose_no": 3, "dose_time": "19:00", "condition_label": "저녁 식후 30분" }
        ]
      },
      {
        "prescription_item_id": 1302,
        "drug_id": 2048,
        "drug_name": "새싹캡슐",
        "dose_text": "1캡슐",
        "start_date": "2026-11-20",
        "end_date": "2026-12-19",
        "is_as_needed": false,
        "schedule_status": "ok",
        "schedules": [
          { "condition_id": 5004, "dose_no": 1, "dose_time": "23:00", "condition_label": "취침 전" }
        ]
      },
      {
        "prescription_item_id": 1303,
        "drug_id": null,
        "drug_name": "햇살시럽",
        "dose_text": "5mL",
        "start_date": "2026-11-20",
        "end_date": "2026-11-24",
        "is_as_needed": true,
        "schedule_status": null,
        "schedules": []
      }
    ],
    "conditions_to_confirm": [],
    "uses_default_routine": true,
    "first_intake_at": "2026-11-20T19:00:00+09:00"
  }
  ```
  위 예시는 18:00에 등록한 경우라 첫 복용이 그날 저녁 19:00입니다. `conditions_to_confirm`은 6장 확정 응답과 같은 칸이며, 직접 입력은 끼니를 꼭 고르므로 항상 빈 배열입니다.
- 에러: `VALIDATION_ERROR`(422) → `fields`의 항목 아래에 사유 표시(경로 예: `drugs[0].total_days`) / `DRUG_NOT_FOUND`(422) 보낸 `drug_id`가 `drugs`에 없음 → 약 다시 검색 / `PRESCRIPTION_ALREADY_ENDED`(422) → 시작일 확인 안내
- 비고:
  - `end_date`는 ERD에 칸이 없어 `start_date + total_days − 1`로 계산해서 내려줍니다.
  - `schedule_status`는 ERD `schedule_status`(`ok / needs_check`) 값을 약 단위로 모은 것입니다. 회차 하나라도 `needs_check`이면 `needs_check`, 필요시 약은 시간표가 없어 `null`입니다.
  - 가이드 행 2개(`medication`, `lifestyle`)는 처방과 같은 트랜잭션에서 `generating`으로 만들어지고, 생성 작업은 응답을 보낸 뒤 시작됩니다(7-7). 저장 후 진행 상태는 7-1(`GET /prescriptions/{prescription_id}/guides`)로 확인합니다.
  - 처방 상세 화면용 전체 데이터는 `GET /prescriptions/{prescription_id}`(설아)로 받습니다. 저장 후 프론트는 홈으로 이동합니다(11/20 결정). 등록하자마자 약통에 칸이 생기는 것이 바로 보이고, 가이드는 홈 상단 "가이드를 만들고 있어요" 안내로 알려 줍니다.
  - 건강 프로필이 없을 때의 팝업(REQ-USER-010 예외)은 프론트가 `GET /users/me/health-profile`의 `is_registered`로 판단해 이 API를 부르기 전에 띄웁니다(11/23 설아님 동의, 와이어프레임도 이 기준).
  - 직접 입력은 처방일이 보통 `null`이라, 가이드 목록(7-3)은 처방일이 없으면 등록일(`created_at`)을 "○월 ○일 등록"으로 보여줍니다(11/23 설아님 결정).
  - 저장 버튼 연타로 같은 처방이 두 번 생기지 않게 프론트에서 저장 중 버튼을 막습니다. 서버 쪽 중복 방지(`Idempotency-Key`)는 2차입니다.
  - 1차 범위 밖: 식간·공복·n시간 간격 조건, 매일이 아닌 주기, 복용법 문장 해석(`POST /dosage/parse`), 병용 주의 확인(REQ-MED-007)은 2차입니다.

### [내부] create_prescription()
- 설명: 처방 저장 → 시간표 계산 → 복용 기록 생성 → 가이드 행 생성·작업 등록을 한 트랜잭션에서 처리합니다. OCR 확정과 직접 입력이 모두 이 함수를 불러 저장 로직이 하나로 유지됩니다.
- 관련 요구사항: REQ-OCR-004, REQ-MED-001, REQ-MED-008, REQ-MED-009
- 부르는 곳: `POST /prescriptions`(민정), `POST /scans/{scan_id}/confirm`(채민)
- 관련 테이블: `prescriptions`, `prescription_items`, `dose_conditions`, `dose_schedules`, `intake_logs`, `medical_documents`(OCR일 때 확정 처리), `guides`(`start_guide_generation()`이 생성)
- 위치(제안): `app/services/prescription_service.py`
- 시그니처:

  ```python
  async def create_prescription(
      db: AsyncSession,
      user_id: int,
      data: PrescriptionIn,
      *,
      source: Literal["ocr", "manual"],          # prescriptions.source
      background_tasks: BackgroundTasks,         # 가이드 생성 작업 등록용(7-7)
      medical_document_id: int | None = None,    # OCR 확정일 때만 → prescriptions.document_id
      now: datetime | None = None,               # 테스트용. None이면 현재 KST
  ) -> PrescriptionCreated: ...
  ```
- 입력 형식: 6장 확정 API Request Body와 같은 모양입니다(채민님 제안 수용). 직접 입력도 같은 모양을 씁니다.

  ```python
  class DoseIn(BaseModel):
      dose_no: int                               # 1부터
      meal: Literal["breakfast", "lunch", "dinner"] | None = None
      timing: Literal["after_meal", "before_meal", "bedtime"] | None = None  # None = 복용 조건 확인 필요
      offset_min: int | None = None

  class CycleIn(BaseModel):
      type: Literal["daily"]                     # 1차는 daily만
      start_date: date

  class DosageIn(BaseModel):
      parsed_by: Literal["rule", "user"]          # ERD v2. LLM 해석은 2차(4-8 E9)
      as_needed: bool = False
      doses: list[DoseIn]                        # 필요시 약은 빈 배열
      cycle: CycleIn

  class DosePerTimeIn(BaseModel):
      text: str
      min: Decimal | None = None
      max: Decimal | None = None
      unit: str | None = None
      parsed: bool

  class DrugIn(BaseModel):
      line_no: int | None = None                 # OCR만. 저장하지 않음
      drug_id: int | None                        # 공공데이터에 없는 약은 None
      drug_name: str
      raw_text: str | None = None                # OCR 원문 줄. 있으면 저장
      dose_per_time: DosePerTimeIn
      times_per_day: int | None                  # 1~4. 필요시 약(as_needed)만 None 허용(4-8 E10)
      total_days: int
      instruction_text: str | None = None        # OCR 원문 복용법(예: "식후30분")
      dosage: DosageIn

  class PrescriptionIn(BaseModel):
      hospital_name: str | None = None
      prescribed_date: date | None = None
      memo: str | None = None                    # 직접 입력만
      drugs: list[DrugIn]
  ```
- 입력 → ERD 저장 매핑(필드 이름을 ERD로 바꾸는 곳은 이 함수 한 곳뿐입니다):

  | 입력 | ERD 컬럼 |
  | --- | --- |
  | `hospital_name`, `prescribed_date`, `memo` | `prescriptions` 같은 이름 |
  | `medical_document_id` | `prescriptions.document_id` |
  | `drugs[].drug_id` | `prescription_items.drug_id` |
  | `drugs[].drug_name` | `prescription_items.drug_name_raw` |
  | `drugs[].raw_text` | `prescription_items.source_text` |
  | `dose_per_time.text` | `prescription_items.dose_text` |
  | `dose_per_time.min` | `prescription_items.dose_amount`(`parsed: true`이고 `min = max`일 때만, 아니면 `NULL`) |
  | `dose_per_time.unit` | `prescription_items.dose_unit` |
  | `times_per_day`, `total_days` | `prescription_items` 같은 이름 |
  | `dosage.cycle.start_date` | `prescription_items.start_date` |
  | `doses[].dose_no` | `dose_conditions.slot_no` |
  | `doses[].timing` | `dose_conditions.condition_type`(`None`이면 `NULL` = 확인 필요) |
  | `doses[].meal` | `dose_conditions.meal` |
  | `doses[].offset_min` | `dose_conditions.offset_minutes` |
  | `dosage.as_needed: true` | `dose_conditions` 1행(`slot_no = 1`, `condition_type = as_needed`) |
  | `dosage.parsed_by` | `dose_conditions.parsed_by` 같은 값(`rule` / `user`, 4-8 E9) |
  | `instruction_text` | 그 약 모든 회차의 `dose_conditions.source_phrase` |
  | (함수가 정함) | `time_basis`: 시각을 계산할 수 있으면 `prescription`, 확인 필요면 `needs_check` / `user_confirmed`: `condition_type`이 있으면 `true` |
- 반환:

  ```python
  class PrescriptionCreated(BaseModel):
      prescription_id: int
      items: list[CreatedItem]                   # prescription_item_id, is_as_needed, schedule_status, schedules
      conditions_to_confirm: list[ConditionToConfirm]  # 6장 확정 응답에 그대로 사용
      intake_count: int                          # 만든 intake_logs 수
      first_intake_at: datetime | None
      guide_ids: dict[str, int]                  # {"medication": 9001, "lifestyle": 9002}

  class ConditionToConfirm(BaseModel):
      condition_id: int                          # dose_conditions.id
      prescription_item_id: int
      drug_name: str
      dose_no: int
      reason: Literal["meal_unknown", "timing_unknown"]
  ```
- 처리 순서(한 트랜잭션):
  1. 입력 검증. 두 API 공통 규칙(약 1개 이상, `drug_name`·`dose_per_time.text` 빈칸 불가, `times_per_day` 1~4(필요시 약만 `None` 가능), `total_days` 1~365, `cycle.type = daily`, `timing` 허용 값, `drug_id`가 있으면 `drugs.is_oral = false`인 약은 거절(먹는 약만, ERD v2))을 검사합니다. 약 한 줄 단위 검사는 `validate_drug_input(drug, *, index, manual)`(`app/services/prescription_service.py`)로 뺍니다. `index`는 에러 경로(`drugs[1].total_days`)를 만들 때 쓰고, `manual=True`면 직접 입력 규칙(`POST /prescriptions` 표)까지 검사합니다. `create_prescription()`이 약마다 `manual=(source == "manual")`로 직접 부르므로, 부르는 API는 따로 검사하지 않아도 됩니다. 실패하면 `PrescriptionValidationError(fields)`를 던지고, 부른 API가 `VALIDATION_ERROR`로 바꿉니다. `fields` 경로는 입력 이름(`drugs[1].total_days`)을 씁니다.
  2. `prescriptions` 저장(`status = active`)
  3. `prescription_items` 저장
  4. `dose_conditions` 회차별 저장
  5. 시간표 계산 → `dose_schedules` 저장. 1차는 `day_type = weekday` 한 행만 만들고 매일 같은 시각을 씁니다(ERD). 필요시 회차는 행을 만들지 않습니다.
  6. `intake_logs` 생성: 시작일부터 종료일까지 매일 × `status = ok`인 회차, **등록 시각 이후 회차만**(6장 합의: 시작일이 과거여도 지난 회차는 만들지 않고 종료일은 그대로). `user_id`, `prescription_item_id`, `dose_condition_id`, `log_date`, `scheduled_time`(= `calculated_time`), `dose_text`(스냅샷), `status = pending`
  7. OCR이면 `medical_documents.status = confirmed`, `confirmed_at = now`, `parsed_result = NULL`로 바꿉니다. 6장 처리 순서 ③(문서 상태 `confirmed`)은 여기서 처리됩니다. `medical_documents`에는 `prescription_id` 칸이 없으므로, `GET /scans/{scan_id}`의 `prescription_id`는 `prescriptions.document_id`로 찾습니다.
  8. `start_guide_generation(db, prescription_id, background_tasks)`(7-7)를 부릅니다. 같은 트랜잭션에서 `guides` 2행을 `generating`으로 만들고 생성 작업을 `background_tasks`에 등록합니다.
  9. flush 후 반환합니다. **커밋은 부른 API가 합니다.** 등록된 가이드 작업은 응답을 보낸 뒤(커밋 뒤) 실행됩니다.
- 시간표 계산 규칙(1차, 규칙 기반이라 같은 입력이면 항상 같은 결과):

  기본 일과: 기상 07:00 / 아침 08:00 / 점심 12:30 / 저녁 18:30 / 취침 23:00

  | `timing`(ERD `condition_type`) | `calculated_time` | `status` | 예 |
  | --- | --- | --- | --- |
  | `after_meal` n분 | 끼니 시각 + n분 | `ok` | 아침 식후 30분 → 08:30 |
  | `before_meal` n분 | 끼니 시각 − n분 | `ok` | 저녁 식전 30분 → 18:00 |
  | `bedtime` | 취침 시각 그대로(몇 분 전인지 임의로 정하지 않음) | `ok` | 23:00 |
  | 필요시(`as_needed`) | `dose_schedules` 행 없음 | - | - |
  | `None`(조건 확인 필요) | `NULL` | `needs_check` | `conditions_to_confirm`에 `timing_unknown` |

  - `meal`이 비어 있을 때: 1일 3회이고 식사 조건이 3개면 `dose_no` 순서대로 아침·점심·저녁, 1일 4회이고 식사 조건 3개 + 취침 전이면 같은 방식으로 채웁니다. 이 경우는 `conditions_to_confirm`에 넣지 않습니다(6장 확정 비고와 같음).
  - 1일 1·2회인데 식전·식후의 `meal`이 비어 있으면 임의로 정하지 않고 `calculated_time = NULL`, `status = needs_check`, `conditions_to_confirm`에 `meal_unknown`으로 넣습니다(REQ-MED-009, 11/20 결정).
  - 한 약에서 회차 하나라도 `needs_check`이면 그 약은 복용 기록을 만들지 않습니다(일부 회차만 체크되는 것을 막기 위함). 모두 고르면 `recalculate_schedule()`이 만듭니다.
  - 2차: 30분 묶음, 회원 일과(`day_type`별 계산), 간격 조건, 매일이 아닌 주기, 일과로 처방 조건을 지킬 수 없을 때 처리
- 예시: 2026-11-20 18:00에 '1일 3회 식후 30분, 3일'을 등록하면 `calculated_time`은 08:30 / 13:00 / 19:00이고, 복용 기록은 11/20 19:00 1개 + 11/21 3개 + 11/22 3개 = 7개입니다.
- 비고:
  - 시간표 계산은 DB를 쓰지 않는 순수 함수 `calculate_schedule(item, routine)`로 분리합니다. 단위 테스트(REQ-NFR-015)와 `recalculate_schedule()`, 2차 일과 재계산(REQ-MED-011)에서 그대로 씁니다.
  - 가이드 행까지 같은 트랜잭션이라, 중간에 실패하면 가이드 행을 포함해 모두 되돌려집니다. OCR이면 문서가 `ocr_done`으로 남아 회원이 다시 [저장하기]를 누를 수 있습니다(6장 확정 비고와 같음).
  - 원본 파일 삭제(6장 ④)는 커밋 뒤에 채민님 코드에서 합니다. 파일 삭제는 DB 트랜잭션으로 되돌릴 수 없기 때문입니다.
  - 개인정보 마스킹(REQ-NFR-004)은 OCR 쪽에서 끝낸 값을 넘겨받습니다. `raw_text`도 `parsed_result`와 같은 마스킹이 적용된 값이어야 합니다.

### [내부] recalculate_schedule()
- 설명: 한 약의 복용 조건이 바뀐 뒤 그 약의 시간표와 앞으로의 복용 기록을 다시 만듭니다. 6장 `PATCH /dose-conditions/{condition_id}`가 요청한 함수입니다(이름도 6장을 따름).
- 관련 요구사항: REQ-MED-008, REQ-MED-009(2차 REQ-MED-011 일과 재계산에도 사용)
- 부르는 곳: `PATCH /dose-conditions/{condition_id}`(채민). 2차: 생활 일과 변경
- 관련 테이블: `dose_conditions`, `dose_schedules`, `intake_logs`, `daily_flowers`
- 시그니처:

  ```python
  async def recalculate_schedule(
      db: AsyncSession,
      prescription_item_id: int,
      *,
      now: datetime | None = None,
  ) -> ScheduleRecalculated: ...

  class ScheduleRecalculated(BaseModel):
      prescription_item_id: int
      schedule_status: Literal["ok", "needs_check"]
      dose_times: dict[int, str | None]          # condition_id → "08:30" (needs_check면 None)
      remaining_to_confirm: int                  # 같은 처방에서 아직 needs_check인 회차 수(6장 응답에 사용)
  ```
- 처리 순서:
  1. 그 약의 `dose_conditions`를 읽어 `calculate_schedule()`로 `dose_schedules`를 갱신합니다.
  2. 그 약의 `intake_logs` 중 지금 이후 회차(`log_date` + `scheduled_time` > now)이면서 `status = pending`인 기록을 지웁니다.
  3. 약 전체가 `ok`이면 지금 이후 ~ 종료일 회차를 다시 만듭니다. 같은 회차(`dose_condition_id`)·같은 날에 이미 `taken`·`missed` 기록이 있으면 만들지 않습니다(이미 먹은 회차가 두 번 생기지 않게). `needs_check`가 남아 있으면 만들지 않습니다.
  4. 오늘 꽃을 다시 판정합니다(`PATCH /intakes`와 같은 함수). 오늘 회차가 새로 생기면 이미 핀 꽃이 지워질 수 있습니다.
  5. 커밋하지 않습니다. `PATCH /dose-conditions`가 조건 변경과 함께 커밋합니다.
- 비고:
  - 6장 요청대로 오늘 이후의 `pending`만 바꾸고 `taken`·`missed`와 지난 기록은 그대로 둡니다.
  - 이미 확인이 끝난 조건을 다시 고칠 때도 같은 함수를 씁니다.
  - 가이드의 `dose_times`는 7-1이 조회할 때 `dose_schedules`에서 다시 읽으므로 이 함수가 가이드를 고칠 필요는 없습니다.

### 4-8. ERD 대조 결과

PR된 `daol_erd_phase1.dbml`과 맞춘 결과입니다.

| 위치 | 이 섹션에서 쓰는 이름 | ERD |
| --- | --- | --- |
| 약관 동의 종류 | `terms / privacy / sensitive_health` | `consent_type` 그대로 |
| 건강 프로필 | `is_pregnant_or_nursing`, `drinks_per_week` 등 | `health_profiles` 그대로 |
| 기저질환 | `condition_code`(`heart / kidney / liver` 등), `condition_text`, '없음'은 빈 배열 | `user_conditions` 그대로(없음 = 행 없음) |
| 처방 입력 | 6장 확정 API와 같은 모양(`drugs[]`, `dose_per_time`, `dosage.doses[]`) | `create_prescription()` 매핑표에서 ERD 이름으로 바꿔 저장 |
| 처방 저장 응답 | `source`, `status`, `schedule_status`(`ok / needs_check`), `is_as_needed` | `prescriptions`, `schedule_status` 그대로 |
| 복용 기록 | `log_date` + `scheduled_time`(스냅샷) | `intake_logs` 그대로. 일시(`scheduled_at`) 칸은 없음 |
| 가이드 상태 | 처방 저장 응답에 넣지 않고 7-1로 조회 | `guides` 종류별 2행 |
| 내 정보 | `profile_image_url`, `talk_message_agreed` 없음 | 1차 ERD에 칸 없음 |
| 약관 동의 | 약관 버전 없음 | 1차 ERD에 칸 없음 |

ERD 쪽에 제안할 것(ERD 담당자 확인):

| No | 테이블 | 제안 | 이유 |
| --- | --- | --- | --- |
| E1 | `users` | `gender`에 enum(`male / female`) 추가 | 지금은 `varchar(10)`이라 값이 정해져 있지 않음 |
| E2 | `users` | ✅ 2차로 미룸. 1차는 기본 아바타만 보여 줌(11/23 설아, 요구사항 USER-002·와이어프레임 반영 완료). 2차 내 정보 화면 때 `profile_image_url varchar(500)` 추가 | REQ-USER-002·008에 '동의한 경우 저장·조회'가 있음 |
| E3 | `user_consents` | `terms_version varchar(20)` 추가 | 약관이 바뀌었을 때 어느 버전에 동의했는지 남겨야 함. 지금은 (회원, 종류) unique라 다시 동의하면 이력도 덮어씀 |
| E4 | `consent_type` | ✅ 1차는 카카오 동의 항목에서 `talk_message`를 빼기로 함(11/23 설아). 1차 enum은 그대로 두고, 2차 알림 때 enum에 추가 | 알림이 2차이고, 요구사항에도 동의 안 한 회원은 알림 설정에서 추가 동의를 받게 되어 있음 |
| E5 | `dose_conditions` | `interval_hours` 칸 정리(1차 `dose_condition_type`에 간격 값이 없음) | 1차에서 쓰지 않는 칸. 6장도 간격을 1차에서 뺌 |
| E6 | `intake_logs` | `(prescription_item_id, log_date, scheduled_time)` unique는 필요시 기록(`scheduled_time = NULL`)에서 PostgreSQL이 NULL끼리 다르게 봐 여러 행이 허용됨. 의도대로라면 note에 적어 두기 | 필요시 약을 하루 여러 번 체크하는 데 필요 |
| E7 | `chat_messages` | note의 `counts_toward_quota` 칸이 테이블에 없음 | 하루 사용량(CHAT-006)이 2차라 2차에 추가해도 됨 |
| E8 | `guides` | ✅ `guide_status`에 `failed` 추가, 실패해도 행 유지(11/20 반영) | 7장 요청 |
| E9 | `parsed_by` | ✅ ERD v2대로 1차는 `rule / user`만 씀. 6장도 1차 LLM 복용법 해석을 빼고 같은 값으로 맞춤(채민님 6장 PR). enum 추가 없음(`llm`은 2차) | 6장과 ERD 값이 달랐음 |
| E10 | `prescription_items` | ✅ `times_per_day`를 NULL 허용으로 바꿈(11/23). 필요시 약만 `NULL` 가능하고, 직접 입력은 지금처럼 하루 최대 횟수를 받음. 공통 테이블 마이그레이션에 반영 | 처방전에 '필요시'만 적힌 약을 저장할 수 없음 |
| E11 | `chat_messages` | ✅ `check_result jsonb` NULL 허용 추가(11/23 채민·유정 동의). `check_full()` 반환값을 그대로 저장: 걸림 `{"passed": false, "types": ["forbidden"], "rules_version": "verify_rules_v1"}`, 통과 `{"passed": true, "types": [], "rules_version": "verify_rules_v1"}`, 검사를 안 했거나 오류면 `NULL`(오류여도 답변은 막지 않음), 회원 질문 행은 항상 `NULL`. 6-4의 `verify_status`·`flagged` 제안은 채민님이 `check_result`로 바꿈. `verify_status`는 2차 정정 안내(VERI-007) 때 다시 논의. 공통 테이블 마이그레이션에 반영 | 칸 하나만 추가하면 되고, 걸린 종류·규칙 버전이 남아 변경 권유 빈도를 볼 수 있음 |

### 4-9. 확인할 것

| No | 확인할 것 | 이 문서의 제안 | 같이 볼 사람 |
| --- | --- | --- | --- |
| 1 | ✅ 첫 로그인 응답의 `is_profile_completed` | 로그인·`GET /users/me` 응답에 넣었습니다. `false`이면 추가 정보 입력 화면으로 보내고, 그 전에는 다른 API가 `PROFILE_REQUIRED`입니다. 프론트는 앱 시작 때 `GET /users/me`로 라우팅(11/23) | 설아 |
| 2 | 리프레시 토큰 쿠키와 동시 재발급 | 동시 재발급: ✅ 프론트 single-flight(11/23). 쿠키: Vercel rewrites로 같은 주소처럼 써서 `SameSite=Lax` 퍼스트파티 쿠키, CORS credentials 불필요(4-1). 첫 배포 때 30MB 업로드·SSE 프록시 통과를 테스트하고, 막히면 Plan B(`daol.site` / `api.daol.site`) | 설아 · 민정 |
| 3 | ✅ 건강 프로필 값 | 7-6 프롬프트에 4장 응답 이름을 그대로 쓰기로 함(11/20) | 유정 |
| 4 | ✅ '최근 3일'의 범위 | 오늘−3일 ~ 오늘(4일치)(11/23) | 설아 |
| 5 | ✅ 지난 날짜 `pending` → `missed` 처리 | 조회·체크 때 갱신. `GET /home?date=`도 같은 함수를 씀(11/23) | 설아 |
| 6 | ✅ 필요시 약 체크 | 1차는 목록만으로 확정. `POST /intakes`는 만들지 않음(11/23) | 설아 |
| 7 | ✅ `intake_logs` 생성 시점 | 확정·등록 시각 이후 회차부터, 시작일이 과거여도 지난 회차는 만들지 않고 종료일은 그대로(6장 합의) | 채민 |
| 8 | ✅ `create_prescription()` 입력 형식 | 6장 확정 API Request Body 모양을 채택하고, ERD 이름으로는 매핑표에서 바꿔 저장합니다. 직접 입력도 같은 모양 | 채민 |
| 9 | ✅ 조건을 고른 뒤 재계산 | `recalculate_schedule(prescription_item_id)`(6장 이름) 명세 추가. 오늘 이후 `pending`만 바꾸고 `taken`·`missed`는 유지 | 채민 |
| 10 | ✅ 처방 약 ID 이름 | `prescription_item_id`로 통일. 5번 섹션의 `prescription_drug_id`는 설아님이 5장 PR에서 바꿈(11/23) | 설아 |
| 11 | ✅ 복용 조건 ID 이름 | 6장대로 `condition_id`(= `dose_conditions.id`)를 씁니다 | 채민 |
| 12 | ✅ 처방 응답의 `schedule_status` | 약 단위로 `ok / needs_check / null(필요시)`. 처방 상세 응답도 같은 값(11/23) | 설아 |
| 13 | 만 14세 미만 가입 | 개인정보보호법상 만 14세 미만은 법정대리인 동의가 필요합니다. 1차는 추가 정보 입력에서 만 14세 미만이면 `VALIDATION_ERROR`로 막습니다(`POST /users/me/profile`에 반영). 설아님 동의(11/23), 채민·유정님 의견 없으면 확정 | 전원 |
| 14 | ✅ `VALIDATION_ERROR`의 `fields` 형식 | `{ "필드 경로": "사유 문장" }`. 1-1에 반영했습니다(11/20) | 전원 |
| 15 | ERD 수정 제안 E1~E11 | 4-8 표. ✅ E2·E4·E8·E9·E10·E11 결정(11/23). E1·E3·E5·E6·E7은 ERD 담당 확인 | ERD 담당 |
| 16 | ✅ 가이드 행이 없는 경우 | 가이드 행을 `create_prescription()` 트랜잭션 안에서 만들어 처방이 있으면 행도 있음. 그래도 없으면 7-1이 `failed`로 내려줌(7-1, 7-7) | 유정 |
| 17 | `start_guide_generation()`에 DB 세션 인자 | 같은 트랜잭션에서 `guides` 행을 만들려면 요청의 세션을 넘겨받아야 합니다. 7-7 시그니처를 `start_guide_generation(db, prescription_id, background_tasks)`로 바꾸는 안 | 유정 |
| 18 | ✅ 직접 입력에서 공공데이터에 없는 약 | 직접 입력도 `drug_id: null` 저장 허용. 화면에 "검색 결과가 없어요 → 이름 그대로 저장" 버튼을 OCR과 같게 둠(11/23) | 설아 |
| 19 | 업로드 장 수·OCR 호출 제한(6장 질문) | 제안값(한 번에 10장, 회원당 하루 20회)에 동의합니다. CLOVA OCR의 PDF 1회 10페이지와도 맞습니다 | 채민 |
| 20 | `GET /drugs` 응답(6장 질문) | 자동완성의 `{"items": [...]}`는 1번 '목록' 규칙의 예외로 1번에 적었습니다. 응답 칸 이름은 ERD `drugs` 컬럼(`item_name`, `ingredient_name`, `company`)에 맞추는 안 | 채민 |
| 21 | ✅ 문서 진행 상태(6장 질문) | ERD `document_status` + 로딩 문구용 `step`에 동의합니다(1-2와 맞음) | 채민 · 설아 |
| 22 | 커밋 위치와 문서 상태 변경 | `create_prescription()`·`recalculate_schedule()`은 커밋하지 않고 부른 API가 커밋합니다. 문서 `confirmed` 처리는 `create_prescription()` 안에서 하므로 6장 처리 순서 ③은 이 함수가 대신합니다. 함수 인자 이름은 6장대로 `medical_document_id` | 채민 |
| 23 | ✅ 홈의 '복용 시간 확인 필요' 약 | 홈에서 바로 끼니를 고름(11/20 설아·채민). `GET /intakes`의 `schedule_check_items`에 회차별 `conditions`(`condition_id`, `dose_no`, `reason`, `timing`, `offset_min`) 추가, 회차마다 `PATCH /dose-conditions` 호출. `timing_unknown`은 안내 카드만 보여 주고 약 상세(C-2)로 보내 거기서 회차마다 `PATCH /dose-conditions`(6장)로 고르며, `conditions` 없이 `reason`·`prescription_id`·`prescription_item_id`를 내려줌(11/23 설아) | 설아 · 채민 |
| 24 | ✅ 약 수정 API(`PATCH /prescription-items`) 1차 제외 | 1차에서 만들지 않음(11/23 채민·설아). '복용 조건 확인 필요' 약은 처방전에서 횟수를 읽었으므로 회차마다 `PATCH /dose-conditions`(6장)로 고르면 됩니다. 약 상세(C-2)도 `PATCH /dose-conditions`를 씁니다. 확인이 끝난 약의 복용법 수정(REQ-MED-004·010)은 2차 | 설아 · 채민 |

<!-- 민정 END -->

---

<!-- 설아 START · 홈·약 정보 -->
## 5. 홈·내 약·처방 조회

담당: 설아 · 관련 화면: A-2, C-1, C-2 · 관련 테이블: `intake_logs`, `daily_flowers`, `dose_schedules`, `dose_conditions`, `prescriptions`, `prescription_items`, `drugs`, `guides`(상태만 조회) · 내부 함수: `get_confirmed_prescription()`

> 1-4 양식으로 작성했습니다. 필드 이름과 enum 값은 1차 ERD(`daol_erd_phase1.dbml`)와 4장 응답 이름에 맞췄습니다.
> 와이어프레임 대조(11/20)대로 홈은 `/home/today` → `GET /home?date=`, 약 상세는 `/drugs/{drug_id}` → `GET /prescription-items/{prescription_item_id}`로 바꿨습니다. `timing_unknown` 약은 약 상세(C-2)에서 6장 `PATCH /dose-conditions`로 회차마다 고칩니다(4-9 24, 별도 수정 API는 1차에 두지 않음).
> `GET /users/me`, `GET·PUT /users/me/health-profile`은 구현만 설아가 맡고 명세는 4장 그대로 씁니다(11/23 공지).

5장을 쓰면서 다른 섹션에 함께 반영한 것(11/23, 각 담당자 확인 부탁드립니다):

| 섹션 | 바꾼 내용 | 담당 |
| --- | --- | --- |
| 4장 | `/home/today` 세 곳 → `/home?date=`, 4-9 23 `timing_unknown` 처리 경로(C-2 + `PATCH /dose-conditions`), 4-9 24 ✅(1차에 만들지 않음) | 민정 |
| 4장 | `create_prescription()` 1단계에 약 한 줄 검사 함수 `validate_drug_input(drug, *, index, manual)` 분리를 적음(`create_prescription()`이 직접 부름) | 민정 |
| 4장 | 문구 함수를 회차용 `format_condition_label()`과 약용 `format_condition_summary()`로 나눔. `/intakes`의 `as_needed_items`·`schedule_check_items` 칸 이름을 `condition_summary`로 바꿈. `get_daily_intakes()` 이름·위치와 커밋 규칙, `schedule_check_items` 규칙을 4장에 적음 | 민정 |
| 6장 | 약 상세 경로를 `GET /prescription-items/{prescription_item_id}`로 수정 | 채민 |
| 6장 | `PATCH /dose-conditions`: 관련 화면에 약 상세(C-2) 추가(C-1 진입 제거), `remaining_to_confirm`이 0이면 홈으로(C-2에서는 약 상세 새로고침), "식전·식후도 골라 주세요"는 약 상세(C-2)로 | 채민 |
| 6장 | `DELETE /scans/{scan_id}`(읽는 중 [취소], 11/20 합의) 추가, 3번 목록에 추가 | 채민 |
| 6장 | 6-1 `confirmed`와 확정 API 비고의 이동 화면 '처방 상세' → '홈'(REQ-OCR-004, 11/23 공지), 5장 `prescription_item_id` 질문 ✅ | 채민 |
| 6장 | 페이지 순서 바꾸기·'처방전이 아닌 것 같아요' 경고 질문에 답변 ✅ | 채민 |
| 7장 | 7-1 `how_to_take` 전체를 조회 때 `get_confirmed_prescription()` 값으로 채우도록 확장(복용 조건을 고쳐도 가이드와 처방이 어긋나지 않게) | 유정 |
| 7장 | 7-1 건강 프로필 문구, 7-7 1회 용량 `min`·`max` 질문 ✅ | 유정 |

### 5-0. 이 섹션의 공통 규칙

**표시용 값**: 화면이 계산하지 않고 서버가 만들어 내려줍니다. 4장 `GET /intakes`와 같은 규칙입니다.

| 값 | 규칙 |
| --- | --- |
| `drug_name` | `drug_id`가 있으면 `drugs.item_name`, 없으면 `prescription_items.drug_name_raw` |
| `ingredient_name` | `drugs.ingredient_name`. 매칭되지 않은 약은 `null`. 화면은 `상품명(성분명)`으로 붙여 보여 줍니다 |
| `has_public_data` | `drug_id`가 있으면 `true`. `false`이면 "이 약은 안내 정보가 없어요"(REQ-OCR-005) |
| `dose_per_time` | `prescription_items.dose_text`를 `parse_dose_text()`(6-4)로 읽은 `{text, min, max, unit, parsed}` |
| `end_date` | `start_date + total_days − 1`(ERD에 칸 없음, 4장과 같음) |
| `remaining_days` | 오늘이 복용 기간 안이면 `end_date − 오늘 + 1`, 시작 전이면 `total_days`, 끝났으면 `0` |
| `condition_label` | `format_condition_label()`. 회차 하나의 문구: `아침 식후 30분`, `저녁 식전 30분`, `취침 전`, 확인 필요면 `복용 조건 확인 필요`(`timing_unknown`) 또는 `식후 30분 · 끼니 확인 필요`(`meal_unknown`) |
| `condition_summary` | `format_condition_summary()`. 약 한 줄의 문구: `1일 3회 식후 30분`, `1일 2회 · 아침 식후 30분, 취침 전`, `필요시 (하루 최대 3회)`, `복용 조건 확인 필요`. 회차 조건이 모두 같으면 묶어서, 다르면 회차 문구를 이어서 씁니다 |
| `schedule_status` | 약 단위 `ok / needs_check / null(필요시)`(4-9 12) |
| `reason` | 회차: `condition_type`이 `NULL`이면 `timing_unknown`, 식전·식후인데 `meal`이 `NULL`이면 `meal_unknown`, 그 외 `null`. 약: 회차 하나라도 `timing_unknown`이면 `timing_unknown`, 아니면 `meal_unknown`, `ok`이면 `null`(4장 `GET /intakes`와 같음) |
| 복용 중 | 시작일과 상관없이 종료일이 오늘 이후인 약. 처방은 복용 중인 약이 하나라도 있으면 복용 중입니다(7-4 '복용 중인 약' 공용 함수와 같은 기준). 1차는 `prescriptions.status`를 바꾸는 작업이 없어서 목록은 날짜로 계산합니다 |

**에러 코드**: 이 섹션은 조회 API만 있어서 1-1 공통 코드(`NOT_FOUND`, `VALIDATION_ERROR` 등)만 씁니다.

### [GET] /api/v1/home?date=
- 설명: 홈(원형 약통) 화면에 필요한 값을 한 번에 돌려줍니다. 날짜를 바꾸면(요일 미니 약통) 같은 API를 그 날짜로 다시 부릅니다.
- 인증: 필요
- 관련 요구사항: REQ-MED-005, REQ-MED-008, REQ-MED-009, REQ-MED-016, REQ-MED-017
- 관련 화면: A-2 홈(상단 요약, 요일 미니 약통, 원형 약통, 화분, 체크리스트, 필요할 때 복용, 기본 일과 배너, 가이드 안내, 빈 상태)
- 관련 테이블: `intake_logs`, `daily_flowers`, `prescription_items`, `dose_conditions`, `dose_schedules`, `drugs`, `prescriptions`, `guides`
- Path / Query: Query `date`(`YYYY-MM-DD`, 생략하면 오늘(KST)). 조회는 오늘−6일 ~ 오늘, 체크·취소는 오늘−3일 ~ 오늘(4장 `GET /intakes`와 같음)
- Request Body: 없음
- Response Body (200): 2026-11-20 18:00에 오늘을 조회한 예시입니다.

  ```json
  {
    "date": "2026-11-20",
    "is_today": true,
    "is_editable": true,
    "uses_default_routine": true,
    "has_active_prescription": true,
    "week": [
      { "date": "2026-11-14", "done_count": 0, "total_count": 0, "bloomed": false },
      { "date": "2026-11-15", "done_count": 0, "total_count": 0, "bloomed": false },
      { "date": "2026-11-16", "done_count": 0, "total_count": 0, "bloomed": false },
      { "date": "2026-11-17", "done_count": 3, "total_count": 3, "bloomed": true },
      { "date": "2026-11-18", "done_count": 2, "total_count": 3, "bloomed": false },
      { "date": "2026-11-19", "done_count": 4, "total_count": 4, "bloomed": true },
      { "date": "2026-11-20", "done_count": 2, "total_count": 4, "bloomed": false }
    ],
    "day_summary": { "log_date": "2026-11-20", "done_count": 2, "total_count": 4 },
    "flower": { "bloomed": false },
    "next_dose": { "scheduled_time": "19:00", "slot_label": "저녁" },
    "slots": [
      {
        "scheduled_time": "08:30",
        "slot_label": "아침",
        "slot_status": "done",
        "items": [
          { "intake_id": 3019, "prescription_id": 512, "prescription_item_id": 1301, "drug_name": "다올정 10mg", "dose_text": "1정", "condition_label": "아침 식후 30분", "status": "taken", "taken_at": "2026-11-20T08:41:05+09:00" }
        ]
      },
      {
        "scheduled_time": "13:00",
        "slot_label": "점심",
        "slot_status": "done",
        "items": [
          { "intake_id": 3020, "prescription_id": 512, "prescription_item_id": 1301, "drug_name": "다올정 10mg", "dose_text": "1정", "condition_label": "점심 식후 30분", "status": "taken", "taken_at": "2026-11-20T13:12:40+09:00" }
        ]
      },
      {
        "scheduled_time": "19:00",
        "slot_label": "저녁",
        "slot_status": "due",
        "items": [
          { "intake_id": 3021, "prescription_id": 512, "prescription_item_id": 1301, "drug_name": "다올정 10mg", "dose_text": "1정", "condition_label": "저녁 식후 30분", "status": "pending", "taken_at": null }
        ]
      },
      {
        "scheduled_time": "23:00",
        "slot_label": "취침 전",
        "slot_status": "due",
        "items": [
          { "intake_id": 3022, "prescription_id": 512, "prescription_item_id": 1302, "drug_name": "새싹캡슐", "dose_text": "1캡슐", "condition_label": "취침 전", "status": "pending", "taken_at": null }
        ]
      }
    ],
    "as_needed_items": [
      { "prescription_item_id": 1303, "drug_name": "햇살정", "dose_text": "1정", "condition_summary": "필요시 (하루 최대 3회)" }
    ],
    "schedule_check_items": [
      {
        "prescription_id": 512,
        "prescription_item_id": 1304,
        "drug_name": "물방울정",
        "dose_text": "1정",
        "condition_summary": "1일 2회 식후 30분",
        "schedule_status": "needs_check",
        "reason": "meal_unknown",
        "conditions": [
          { "condition_id": 5014, "dose_no": 1, "reason": "meal_unknown", "timing": "after_meal", "offset_min": 30 },
          { "condition_id": 5015, "dose_no": 2, "reason": "meal_unknown", "timing": "after_meal", "offset_min": 30 }
        ]
      },
      {
        "prescription_id": 512,
        "prescription_item_id": 1305,
        "drug_name": "구름정",
        "dose_text": "1정",
        "condition_summary": "복용 조건 확인 필요",
        "schedule_status": "needs_check",
        "reason": "timing_unknown"
      }
    ],
    "generating_guides": [
      { "prescription_id": 512, "hospital_name": "다올내과의원" }
    ]
  }
  ```
- 에러: `VALIDATION_ERROR`(422) 날짜 형식 오류 또는 조회 범위 밖 → 날짜 이동 버튼 비활성화로 미리 막습니다
- 비고:
  - `slots`, `as_needed_items`, `schedule_check_items`, `day_summary`, `flower`, `is_editable`, `uses_default_routine`은 4장 `GET /intakes?date=`와 칸 이름·값이 같습니다. 같은 서비스 함수 `get_daily_intakes()`(4장, 민정)를 불러 그대로 담고, 홈에만 필요한 값(`slot_label`, `slot_status`, `week`, `next_dose`, `has_active_prescription`, `generating_guides`)을 더합니다. 지난 날짜 `pending` → `missed` 갱신도 그 함수가 하므로, 조회 API지만 이 API가 커밋합니다(4-9 5).
  - 홈 화면은 이 API만 부릅니다. 칸을 체크하면 `PATCH /intakes/{intake_id}`(4장) 응답의 `day_summary`·`flower`로 화면을 바로 고치고, 끼니를 고르면(`PATCH /dose-conditions`, 6장) 이 API를 다시 부릅니다(4장 `GET /intakes` 비고와 같음).
  - `slot_status`: 원형 약통 칸 상태입니다.

    | 값 | 언제 | 화면 |
    | --- | --- | --- |
    | `done` | 칸 안의 기록이 모두 `taken` | 복용 완료(뚜껑 닫힘 + 체크) |
    | `due` | 아직 다 먹지 않았고 복용 시각 전 | 먹을 차례(뚜껑 열림) |
    | `late` | 아직 다 먹지 않았고, 오늘 복용 시각이 지났거나 지난 날짜 | 시간 지남(연한 경고색). 수정 가능 기간이면 체크할 수 있습니다 |

  - `slot_label`: 칸 안 회차들의 조건이 모두 같은 끼니면 `아침 / 점심 / 저녁`, 모두 취침 전이면 `취침 전`, 섞이면 `null`(화면은 시각만 표시)입니다.
  - `next_dose`: 오늘(`is_today: true`)만 채웁니다. 복용 시각이 지금 이후이고 `done`이 아닌 첫 칸입니다. 없거나 지난 날짜면 `null`입니다. 화면은 지금 시각과 비교해 "저녁까지 1시간"처럼 보여 줍니다.
  - `week`: 선택한 날짜와 상관없이 항상 오늘−6일 ~ 오늘 7일입니다. 개수는 `day_summary`와 같은 규칙(필요시 약 제외)이고, `bloomed`는 `daily_flowers` 행이 있는지입니다. `total_count: 0`이면 빈 동그라미로 보여 줍니다. 날짜별 집계 한 번으로 조회합니다.
  - `schedule_check_items`는 오늘만 담고, 지난 날짜면 빈 배열입니다. 복용 중인 약만 담습니다. `timing_unknown` 카드의 [처방 상세에서 확인하기]는 그 약의 약 상세(C-2, `GET /prescription-items/{prescription_item_id}`)로 보내고, 거기서 회차마다 `PATCH /dose-conditions`(6장)로 고칩니다(4-9 23).
  - `has_active_prescription: false`이면 빈 상태("처방전을 찍어 약을 등록해 보세요" + [처방 등록하기])를 보여 줍니다. 복용 중인 처방은 있는데 그날 칸이 없으면(예: 시작 전) 빈 상태 대신 빈 약통을 보여 줍니다.
  - `generating_guides`: 복약·생활습관 가이드 중 하나라도 `generating`·`verifying`인 처방입니다(7-1 상태 값). 있으면 맨 위에 "약통에 새 약이 들어갔어요 · 가이드를 만들고 있어요"를 띄우고, 누르면 D-2로 갑니다. 홈은 이 값 때문에 다시 부르지 않습니다(진행 상황은 D-2가 7-1로 확인). 7-1의 30초 규칙에 따라 오래된 `generating`은 이 목록에서 뺍니다.
  - 기본 일과 배너(`uses_default_routine: true`)는 1차에 항상 보입니다(REQ-USER-013은 2차).

### [GET] /api/v1/prescriptions
- 설명: 내 약 목록입니다. 처방 묶음마다 약 카드를 함께 돌려줍니다.
- 인증: 필요
- 관련 요구사항: REQ-MED-002
- 관련 화면: C-1 내 약 목록(`복용 중` / `복용 종료` 탭, 처방 묶음 헤더, 약 카드)
- 관련 테이블: `prescriptions`, `prescription_items`, `dose_conditions`, `dose_schedules`, `drugs`, `guides`
- Path / Query: Query `tab`(`active` 복용 중 / `ended` 복용 종료, 기본 `active`), `page`, `size`(1번 공통 규칙)
- Request Body: 없음
- Response Body (200):

  ```json
  {
    "items": [
      {
        "prescription_id": 512,
        "source": "manual",
        "hospital_name": "다올내과의원",
        "prescribed_date": null,
        "created_at": "2026-11-20T18:00:00+09:00",
        "start_date": "2026-11-20",
        "end_date": "2026-12-19",
        "drug_count": 3,
        "needs_check_count": 0,
        "guide_status": "generating",
        "items": [
          { "prescription_item_id": 1301, "drug_id": 1024, "drug_name": "다올정 10mg", "ingredient_name": "다올성분", "has_public_data": true, "condition_summary": "1일 3회 식후 30분", "remaining_days": 30, "is_as_needed": false, "schedule_status": "ok", "reason": null },
          { "prescription_item_id": 1302, "drug_id": 2048, "drug_name": "새싹캡슐", "ingredient_name": "새싹성분", "has_public_data": true, "condition_summary": "1일 1회 취침 전", "remaining_days": 30, "is_as_needed": false, "schedule_status": "ok", "reason": null },
          { "prescription_item_id": 1303, "drug_id": null, "drug_name": "햇살시럽", "ingredient_name": null, "has_public_data": false, "condition_summary": "필요시 (하루 최대 3회)", "remaining_days": 5, "is_as_needed": true, "schedule_status": null, "reason": null }
        ]
      }
    ],
    "page": 1,
    "size": 20,
    "total": 1
  }
  ```
- 에러: `VALIDATION_ERROR`(422) `tab`·`page`·`size` 값 오류
- 비고:
  - 탭 기준은 5-0 '복용 중'입니다. `active`는 복용 중인 약이 하나라도 있는 처방, `ended`는 모든 약이 끝난 처방입니다. `active` 탭의 약 카드에는 끝난 약도 함께 보여 주고 `remaining_days: 0`으로 내려줍니다.
  - 정렬은 처방일(없으면 등록일 `created_at`) 최근 순입니다.
  - `start_date`·`end_date`는 처방 안 약들 중 가장 빠른 시작일·가장 늦은 종료일입니다.
  - 헤더 표시: 처방일이 `null`이면 "○월 ○일 등록"으로 보여 줍니다(7-3과 같음). 병원명이 `null`이면 "병원 이름 없음"입니다.
  - `needs_check_count`는 `schedule_status = needs_check`인 약 수입니다. 0보다 크면 헤더에 "복용 조건 확인 필요"를 보여 줍니다.
  - `guide_status`는 복약 가이드 상태(7-1 값)이고, 행이 없으면 `null`입니다. [가이드 보기]는 상태와 상관없이 D-2로 보냅니다.
  - 결과가 없으면 `items: []`이고, 화면은 "등록한 약이 없어요" + [처방 등록하기]를 보여 줍니다.
  - 처방 수정·삭제(`⋮` 메뉴, REQ-MED-004)와 병용 주의 표시(REQ-MED-007)는 2차입니다.

### [GET] /api/v1/prescriptions/{prescription_id}
- 설명: 처방 상세입니다. 약마다 회차별 복용 조건과 기본 일과로 계산한 복용 시각을 돌려줍니다.
- 인증: 필요
- 관련 요구사항: REQ-MED-002, REQ-MED-008, REQ-MED-009
- 관련 화면: C-1 처방 상세(처방 묶음 헤더를 펼쳤을 때)
- 관련 테이블: `prescriptions`, `prescription_items`, `dose_conditions`, `dose_schedules`, `drugs`, `guides`
- Path / Query: Path `prescription_id`(`prescriptions.id`)
- Request Body: 없음
- Response Body (200):

  ```json
  {
    "prescription_id": 512,
    "source": "ocr",
    "hospital_name": "다올내과의원",
    "prescribed_date": "2026-11-20",
    "memo": null,
    "created_at": "2026-11-20T18:00:00+09:00",
    "start_date": "2026-11-20",
    "end_date": "2026-11-24",
    "is_active": true,
    "uses_default_routine": true,
    "guide": { "medication_status": "completed", "lifestyle_status": "completed" },
    "items": [
      {
        "prescription_item_id": 1301,
        "drug_id": 1024,
        "drug_name": "다올정 10mg",
        "drug_name_raw": "다올정10mg",
        "ingredient_name": "다올성분",
        "has_public_data": true,
        "dose_per_time": { "text": "1정", "min": 1, "max": 1, "unit": "정", "parsed": true },
        "times_per_day": 3,
        "total_days": 5,
        "start_date": "2026-11-20",
        "end_date": "2026-11-24",
        "remaining_days": 5,
        "is_as_needed": false,
        "condition_summary": "1일 3회 식후 30분",
        "schedule_status": "ok",
        "reason": null,
        "doses": [
          { "condition_id": 5001, "dose_no": 1, "timing": "after_meal", "meal": "breakfast", "offset_min": 30, "condition_label": "아침 식후 30분", "dose_time": "08:30", "schedule_status": "ok", "reason": null },
          { "condition_id": 5002, "dose_no": 2, "timing": "after_meal", "meal": "lunch", "offset_min": 30, "condition_label": "점심 식후 30분", "dose_time": "13:00", "schedule_status": "ok", "reason": null },
          { "condition_id": 5003, "dose_no": 3, "timing": "after_meal", "meal": "dinner", "offset_min": 30, "condition_label": "저녁 식후 30분", "dose_time": "19:00", "schedule_status": "ok", "reason": null }
        ]
      },
      {
        "prescription_item_id": 1305,
        "drug_id": 3071,
        "drug_name": "구름정",
        "drug_name_raw": "구름정",
        "ingredient_name": "구름성분",
        "has_public_data": true,
        "dose_per_time": { "text": "1정", "min": 1, "max": 1, "unit": "정", "parsed": true },
        "times_per_day": 2,
        "total_days": 5,
        "start_date": "2026-11-20",
        "end_date": "2026-11-24",
        "remaining_days": 5,
        "is_as_needed": false,
        "condition_summary": "복용 조건 확인 필요",
        "schedule_status": "needs_check",
        "reason": "timing_unknown",
        "doses": [
          { "condition_id": 5016, "dose_no": 1, "timing": null, "meal": null, "offset_min": null, "condition_label": "복용 조건 확인 필요", "dose_time": null, "schedule_status": "needs_check", "reason": "timing_unknown" },
          { "condition_id": 5017, "dose_no": 2, "timing": null, "meal": null, "offset_min": null, "condition_label": "복용 조건 확인 필요", "dose_time": null, "schedule_status": "needs_check", "reason": "timing_unknown" }
        ]
      }
    ]
  }
  ```
- 에러: `NOT_FOUND`(404) 없는 처방·다른 회원의 처방 → "처방을 찾을 수 없어요" 후 내 약 목록으로 이동
- 비고:
  - `get_confirmed_prescription()`과 같은 조회 함수로 읽습니다(아래 내부 함수). 화면과 가이드·검증이 같은 처방 데이터를 쓰게 하기 위함입니다.
  - `dose_time`은 `dose_schedules.calculated_time`(1차 `day_type = weekday` 한 행)을 읽기만 합니다. `needs_check` 회차와 필요시 약은 `null`입니다. 필요시 약은 `doses: []`입니다.
  - 약 순서는 `prescription_items.id` 순(처방전 줄 순서)입니다.
  - `schedule_status = needs_check`인 약은 "복용 조건 확인 필요"를 표시하고, 카드를 누르면 약 상세(C-2)에서 고칩니다.
  - `guide`의 두 값은 7-1 상태 값이고, 행이 없으면 `null`입니다. 가이드 본문은 [가이드 보기] → 7-1로 받습니다.
  - `is_active`는 5-0 '복용 중' 기준입니다.

### [GET] /api/v1/prescription-items/{prescription_item_id}
- 설명: 약 상세입니다. 내 복용 정보(회차별 조건·복용 시각·남은 일수)와 공공데이터 약 정보를 함께 돌려줍니다.
- 인증: 필요
- 관련 요구사항: REQ-MED-002, REQ-OCR-005
- 관련 화면: C-2 약 상세 정보, A-2 홈의 `timing_unknown` 카드에서 진입(복용 조건 고르기는 6장 `PATCH /dose-conditions`)
- 관련 테이블: `prescription_items`, `prescriptions`, `dose_conditions`, `dose_schedules`, `drugs`
- Path / Query: Path `prescription_item_id`(`prescription_items.id`)
- Request Body: 없음
- Response Body (200):

  ```json
  {
    "prescription_item_id": 1301,
    "prescription": { "prescription_id": 512, "hospital_name": "다올내과의원", "prescribed_date": "2026-11-20", "created_at": "2026-11-20T18:00:00+09:00" },
    "drug_id": 1024,
    "drug_name": "다올정 10mg",
    "drug_name_raw": "다올정10mg",
    "ingredient_name": "다올성분",
    "company": "다올제약",
    "image_url": "https://.../daol10.jpg",
    "has_public_data": true,
    "dose_per_time": { "text": "1정", "min": 1, "max": 1, "unit": "정", "parsed": true },
    "times_per_day": 3,
    "total_days": 5,
    "start_date": "2026-11-20",
    "end_date": "2026-11-24",
    "remaining_days": 5,
    "is_as_needed": false,
    "condition_summary": "1일 3회 식후 30분",
    "schedule_status": "ok",
    "reason": null,
    "doses": [
      { "condition_id": 5001, "dose_no": 1, "timing": "after_meal", "meal": "breakfast", "offset_min": 30, "condition_label": "아침 식후 30분", "dose_time": "08:30", "schedule_status": "ok", "reason": null },
      { "condition_id": 5002, "dose_no": 2, "timing": "after_meal", "meal": "lunch", "offset_min": 30, "condition_label": "점심 식후 30분", "dose_time": "13:00", "schedule_status": "ok", "reason": null },
      { "condition_id": 5003, "dose_no": 3, "timing": "after_meal", "meal": "dinner", "offset_min": 30, "condition_label": "저녁 식후 30분", "dose_time": "19:00", "schedule_status": "ok", "reason": null }
    ],
    "drug_info": {
      "efficacy": "…",
      "usage_text": "…",
      "precautions": "…",
      "side_effects": "…",
      "storage_method": "…",
      "source_name": "식품의약품안전처 의약품개요정보(e약은요)",
      "data_fetched_at": "2026-11-01"
    }
  }
  ```
  공공데이터에 없는 약(`drug_id: null`)은 `has_public_data: false`이고 `ingredient_name`·`company`·`image_url`·`drug_info`가 `null`입니다.
- 에러: `NOT_FOUND`(404) 없는 약·다른 회원의 약 → "약 정보를 찾을 수 없어요" 후 내 약 목록으로 이동
- 비고:
  - 처방 상세와 같은 조회 함수로 읽고, 약 한 줄만 골라 `drugs` 칸을 더합니다.
  - `drug_info` 칸은 `drugs` 컬럼 이름을 그대로 씁니다. 비어 있는 칸은 `null`이고, 화면은 그 섹션을 숨깁니다. 하단에 `출처: {source_name} · {data_fetched_at} 기준`을 표시합니다(REQ-MED-002). `source_name`은 약마다 달라질 수 있어서 `drugs.data_source`로 정합니다: `easy_drug` → "식품의약품안전처 의약품개요정보(e약은요)", `permit` → "식품의약품안전처 의약품 허가정보"(e약은요에 없는 처방약을 허가정보로 보충). 기준일은 `drugs.data_fetched_at`(우리가 받아 온 날)이고, `drugs.source_updated_at`(식약처 수정일)은 화면에 쓰지 않습니다(11/23 유정·민정).
  - `drug_info: null`이면 "이 약은 안내 정보가 없어요" + 내 복용 정보 카드만 보여 줍니다.
  - `schedule_status = needs_check`이면 내 복용 정보 카드에서 `reason`이 있는 회차마다 고르기 칩을 보여 주고, 그 회차의 `condition_id`로 6장 `PATCH /dose-conditions/{condition_id}`를 부릅니다. `timing_unknown` 회차는 식전·식후·취침 전과 끼니·분을, `meal_unknown` 회차는 끼니만 고릅니다(B-2 이어서 고르기와 같은 칩). 저장할 때마다 이 API를 다시 불러 화면을 갱신합니다.
  - 하루 횟수·필요시 여부·용량·일수는 B-2에서 저장 전에 확인한 값이라 1차에서는 고치지 않습니다. 확인이 끝난 약의 복용 시각·복용법 수정(REQ-MED-010, REQ-MED-004)은 2차입니다.
  - `image_url`은 공공데이터의 낱알 이미지 주소이며, 없으면 `null`이고 화면은 기본 약 그림을 씁니다.

### [내부] get_confirmed_prescription()
- 설명: 확정된 처방 하나를 회차별 복용 조건·복용 시각까지 담아 돌려줍니다. 가이드 생성(7-7)·가이드 검증(`verify_guide()`, 6장)·가이드 조회(7-1)가 같은 값을 쓰게 하는 공용 함수입니다.
- 관련 요구사항: REQ-OCR-004, REQ-MED-008, REQ-GUIDE-001, REQ-VERI-001
- 부르는 곳: 7-7 `run_guide_generation()`(유정), 7-1 조회(`how_to_take` 채우기), 6장 `verify_guide()`의 `prescription` 입력(채민)
- 관련 테이블: `prescriptions`, `prescription_items`, `dose_conditions`, `dose_schedules`, `drugs`
- 위치(제안): `app/services/prescription_query.py`
- 시그니처:

  ```python
  async def get_confirmed_prescription(
      db: AsyncSession,
      prescription_id: int,
      *,
      user_id: int | None = None,   # 넘기면 소유 확인. 백그라운드 작업은 None
  ) -> dict: ...
  ```
- 반환: `GET /prescriptions/{prescription_id}` 응답에서 화면 전용 칸(`memo`, `guide`, `created_at`, `uses_default_routine`, `is_active`)을 뺀 값입니다. AI 파트 기획 문서 4-3 확정본·4-9 형식이며 칸 이름은 6·7장과 같습니다.

  ```python
  {
      "prescription_id": 512,
      "user_id": 17,
      "hospital_name": "다올내과의원",
      "prescribed_date": "2026-11-20",      # date → ISO 문자열
      "drugs": [
          {
              "prescription_item_id": 1301,
              "drug_id": 1024,               # 없으면 None
              "drug_name": "다올정 10mg",     # 5-0 표시 규칙
              "ingredient_name": "다올성분",
              "has_public_data": True,
              "dose_per_time": {"text": "1정", "min": 1, "max": 1, "unit": "정", "parsed": True},
              "times_per_day": 3,            # 필요시 약은 하루 최대 횟수 또는 None
              "total_days": 5,
              "start_date": "2026-11-20",
              "end_date": "2026-11-24",
              "is_as_needed": False,
              "schedule_status": "ok",       # ok / needs_check / None(필요시)
              "condition_summary": "1일 3회 식후 30분",
              "doses": [
                  {"condition_id": 5001, "dose_no": 1, "timing": "after_meal", "meal": "breakfast",
                   "offset_min": 30, "dose_time": "08:30", "schedule_status": "ok", "reason": None},
              ],
          },
      ],
  }
  ```
- 에러: 처방이 없거나 `user_id`가 다르면 `PrescriptionNotFound`를 던집니다. API에서는 `NOT_FOUND`(404)로 바꾸고, 7-7에서는 그 가이드를 `failed`로 처리합니다.
- 비고:
  - 7-1은 가이드를 조회할 때마다 이 함수로 `how_to_take`를 채웁니다.
  - 처방 상세 API와 같은 조회 함수 하나(`load_prescription(db, prescription_id)`)를 쓰고, 반환 모양만 다르게 만듭니다. 한 번의 조회로 약·회차·시간표·`drugs`를 함께 읽습니다(N+1 방지).
  - `dose_per_time`의 `min`·`max`·`parsed`는 ERD에 칸이 없어 `dose_text`를 `parse_dose_text()`(6-4, 채민)로 읽어 만듭니다(7-7 비고·6장 답변). 같은 글자면 항상 같은 결과입니다.
  - `dose_time`은 `dose_schedules`를 읽기만 합니다(계산은 4장 `calculate_schedule()`).
  - 값은 JSON으로 바로 넣을 수 있도록 날짜를 문자열로, `Decimal`을 숫자로 바꿔 돌려줍니다(가이드 프롬프트·검증 입력용).
  - DB를 바꾸지 않고 커밋하지 않습니다.

<!-- 설아 END -->

---

<!-- 채민 START · 처방 등록·검증 -->
## 6. 처방 등록·검증 (AI A)

담당: 채민 · 관련 화면: B-1, B-2, A-2(홈 끼니 고르기) · 관련 테이블: `medical_documents`, `document_pages`, `drugs`, `prescriptions`·`prescription_items`·`dose_conditions`(확정 시 생성), `dose_schedules`·`intake_logs`(복용 조건 수정 시 다시 계산) · 내부 함수: `verify_guide()`, `parse_dose_text()`, `mask_text()`, `check_full()`(6-4)

> AI 파트 기획 문서 v5의 6-1(AI A), 4-3, 4-10, 11-2를 1-4 양식으로 옮겨 적습니다.

> 퇴원요약지(OCR-006·007)는 범위에서 빠졌으므로 문서 종류는 `prescription`(처방전) / `pill_envelope`(약봉투) 두 가지만 받습니다. AI 문서 4-3의 `diagnoses[]`·`discharge_notes[]`·`excluded_drugs[]`와 페이지 순서 바꾸기는 넣지 않았습니다.
> AI 문서 4-3에서 바꾼 점: `scan_id`는 숫자(`medical_documents.id`), 약품 매칭은 `drug_code` 대신 `drug_id`(`drugs.id`)를 씁니다(1번 공통 규칙). 감량 단계(`taper_steps`)·간격(`interval_hours`)·약 형태(`form`)는 1차 직접 입력 범위에 맞춰 뺐습니다.

| 확인할 것 | 같이 볼 사람 |
| --- | --- |
| ✅ 확정 API는 채민님이 맡고, 저장은 민정님의 `create_prescription()`을 부릅니다(AI 문서 D11, 11/20). 채민님은 인식 결과를 이 함수의 입력 형식으로 넘기고 원본을 삭제합니다 | 민정 · 유정 |
| ✅ `create_prescription()` 입력 형식은 `POST /scans/{scan_id}/confirm` Request Body와 같은 모양입니다. 직접 입력도 같은 모양이고 `source`만 다릅니다(4장 4-9 #8) | 민정 |
| ✅ 약 검색은 `GET /drugs?q=&limit=` 하나로 처리합니다. 자동완성이라 `{"items": [...]}`만 돌려주는 예외를 1번 '목록' 규칙에 적었습니다(4장 4-9 #20). 응답 칸 이름은 ERD `drugs` 컬럼(`item_name`, `ingredient_name`, `company`)에 맞췄습니다 | 민정 · 설아 |
| ✅ 진행 상태 값: 1-2 규칙대로 ERD `document_status`(`uploaded / ocr_done / ocr_failed / confirmed / expired`)를 그대로 쓰고, 로딩 문구용으로 `step`(`reading / structuring`)을 따로 둡니다(6-1, 4장 4-9 #21) | 민정 · 설아 |
| 칸별 신뢰도 `{value, confidence, needs_check}`로 확인 화면의 노란색 강조를 표시합니다(6-2) | 설아 |
| 원본 이미지 API는 인증 헤더가 필요해서 `<img src>`로 바로 쓸 수 없습니다. `fetch`로 받아 blob URL로 띄워 주세요 | 설아 |
| ✅ 업로드는 한 번에 10장, OCR 호출은 회원당 하루 20회입니다(4장 4-9 #19, CLOVA OCR의 PDF 1회 10페이지와도 맞음) | 민정 |
| ✅ 복용 기록은 확정 시각 이후 회차부터 만듭니다. 복용 시작일이 과거여도 지난 회차는 만들지 않고, 종료일(시작일 + 총 일수)은 그대로 둡니다(4장 4-9 #7) | 민정 |
| ✅ `dose_conditions` 한 행 = 약 한 줄의 회차 하나이고, ID 이름은 `condition_id`입니다. 조건을 바꾼 뒤 재계산은 4장 `recalculate_schedule(db, prescription_item_id)`를 부릅니다(4장 4-9 #9·#11) | 민정 |
| 1차 시간표가 계산하지 않는 조건(식간·공복·n시간 간격, 매일이 아닌 주기)은 인식은 하되 `needs_confirm: true`로 보내고, 확정 때는 1차 허용 값만 받습니다(6-2) | 민정 · 설아 |
| 공공데이터에 없는 약(`drug_id: null`)도 이름 그대로 저장할 수 있게 했습니다. 이 약의 가이드는 "이 약은 안내 정보가 없어요"로 나갑니다 | 민정 · 유정 |
| ✅ `verify_guide()`를 7장에 맞췄습니다(11/20 유정님과 합의): 칸 이름 `prescription_item_id`·`guide_id`, `kind="lifestyle"`이면 금지 표현만 검사, `user_conditions` 입력, `fallback_drug_ids` 없음(약 단위 실패는 코드 오류 → `failed`), 문장 바꾸기는 7-1 비고 표를 따름 | 유정 |
| 1차는 다시 쓰기가 없어 `verify_guide()`에 `attempt_no`·`is_last_attempt`를 두지 않았습니다. 7-7 검증 호출에서 두 인자를 빼 주세요 | 유정 |
| ✅ 가이드 `dose_times`는 조회 때 시간표 값으로 채웁니다(7-1 반영, 11/20). 그래서 복용 조건을 바꿔도 가이드와 어긋나지 않고, `verify_guide()`도 `dose_times`를 검사하지 않습니다 | 유정 |
| 7-7 질문에 대한 답: 1회 용량 `min`·`max`·`parsed`는 공용 함수 `parse_dose_text()`(6-4)로 만듭니다. 확정 API·`PATCH /scans`·`get_confirmed_prescription()`이 같은 함수를 써서 결과가 어긋나지 않게 합니다 | 설아 · 유정 |
| ✅ 5장 `get_confirmed_prescription()` 반환 형식의 `prescription_drug_id`를 6·7장과 같은 `prescription_item_id`로 맞췄습니다(11/23 5장 작성) | 설아 |
| ✅ 끼니 기본값은 4장 순수 함수 `fill_default_meals(doses, times_per_day)`(민정, DB 안 씀)로 채웁니다. `create_prescription()`이 저장 전에 부르고, `GET /scans/{scan_id}`도 같은 함수로 미리 채워 보여 줍니다(민정님 답변) | 민정 · 재경 |
| ✅ 홈의 끼니 고르기도 `PATCH /dose-conditions/{condition_id}`를 씁니다. 끼니만 보내도 되도록 부분 수정으로 바꿨습니다. 홈의 `schedule_check_items`에 `conditions: [{condition_id, dose_no, reason}]`을 넣기로 했습니다(4장 설아님 리뷰). `reason`은 확정 응답·`ConditionToConfirm`과 같은 값입니다 | 설아 · 민정 |
| ✅ ERD v2(`daol_erd_v2.dbml`)에 맞췄습니다: `parsed_by`는 `rule` / `user`(LLM 복용법 해석은 ERD대로 2차), 문서 종류 `pill_envelope`, 확정 Body `drug_name`은 처방전에 적힌 이름(`drug_name_raw`), 원문 줄 `raw_text`(`source_text`), `is_oral`('먹는 약 아님'), `times_per_day` 1~4·`total_days` 1~365, 프롬프트 버전 `parse_document_v1`(`prompt_kind`) | 민정 · 유정 |
| 1차는 사전에 없는 복용법 문장을 LLM으로 해석하지 않고 바로 '복용 조건 확인 필요'로 둡니다(ERD `parsed_by.llm` [2차]). AI 기획 문서의 1차 복용법 해석(LLM) 범위도 2차로 옮겨야 합니다 → 유정님과 AI 문서 반영 | 유정 · 민정 |
| ✅ ERD 칸 이름에 맞춰 `document_type` → `doc_type`, `expires_at` → `image_delete_due_at`으로 바꿨습니다(1번 공통 규칙, 민정님 답변). `prescribed_date`는 `prescriptions.prescribed_date`로 저장되므로 그대로 둡니다 | 민정 |
| ✅ 같은 파일 다시 올리기 감지("이미 올린 사진이에요", `file_hash`)와 여러 장의 병원명·처방일이 다를 때 "다른 처방전이 섞여 있는 것 같아요" 안내는 2차입니다(11/23 설아, REQ-OCR-001). 1차는 `file_hash` 값만 저장합니다. 2차에 넣을 때는 `POST /scans`에서 막지 않고 응답에 `duplicate_pages: [1]`로 알려 주는 안을 씁니다 | 설아 · 민정 |
| ✅ 페이지 순서는 업로드 화면(B-1-1)의 ↑↓로 정하고 올린 순서가 `page_no`가 되므로 확인 화면에서는 바꾸지 않습니다. '처방전이 아닌 것 같아요'는 따로 경고하지 않고 `no_drug_found` 실패 화면의 문서 종류 다시 고르기로 대신합니다(11/23 설아, 와이어프레임 B-1) | 설아 |


### 6-1. 진행 상태 (`document_status` + `step`)

| `status` | `step` | 화면 | 다음 행동 |
| --- | --- | --- | --- |
| `uploaded` | `reading` | "처방전을 읽고 있어요" | 2초마다 다시 조회 |
| `uploaded` | `structuring` | "약 정보를 정리하고 있어요" | 2초마다 다시 조회 |
| `ocr_done` | `null` | 인식 결과 확인 화면(B-2) | 회원이 확인·수정 후 확정 |
| `ocr_failed` | `null` | `message` + [다시 찍기] / [직접 입력하기] | B-1으로 돌아가거나 직접 입력(`POST /prescriptions`) |
| `confirmed` | `null` | 홈으로 이동 | `prescription_id` 사용 |
| `expired` | `null` | "파일이 삭제됐어요. 다시 올려 주세요" | B-1 |

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
| 회원이 고친 칸 | `null` | 항상 `false`. 단, 고친 용량을 읽을 수 없거나(`parsed: false`) 정·캡슐·포 0.25 미만이면 `true` |

**용량**(`dose_per_time`): AI 문서 4-9 모양 `{text, min, max, unit, parsed}`에 `confidence`, `needs_check`를 더합니다. `parsed: false`(적당량 등)면 `needs_check: true`이고 "용량을 확인해 주세요"를 띄웁니다. 정·캡슐·포인데 `min`이 0.25 미만(예: `0.1정`)이어도 OCR이 숫자를 잘못 읽었을 수 있어 `needs_check: true`입니다(OCR 용량·고친 용량 모두, 확정은 막지 않음). 용량은 필수 칸이 아니라 그대로 확정할 수 있습니다. 회원이 고친 용량(직접 추가한 줄 포함)은 `edited: true`이고, 이 용량을 읽을 수 없을 때는 OCR 칸과 다른 문구 "숫자와 단위로 적어 주시면 더 정확해요 (예: 1정, 0.5정, 5mL)"를 띄웁니다(화면 문구는 프론트에서 정함, 11/25 설아). OCR 용량은 `edited: false`입니다.

**약품 매칭**(`match`):

| `status` | 뜻 | 화면 |
| --- | --- | --- |
| `exact` | 약품 DB와 정확히 일치. `drug_id`가 채워짐 | 확인 불필요 |
| `candidates` | 비슷한 약 최대 3개(`candidates[]`) | 후보 3개 중 고르기 + [다른 약 검색] |
| `none` | 비슷한 약 없음 | "등록되지 않은 약품이에요" + [약 검색] (`GET /drugs`) |

**먹는 약 여부**(`is_oral`): 매칭된 약의 `drugs.is_oral`을 그대로 줍니다(OCR-003·004, 1차는 먹는 약만).

| `is_oral` | 화면 | 확정 |
| --- | --- | --- |
| `true` | 그대로 표시 | 저장 |
| `false` | 회색 + "먹는 약이 아니라 등록되지 않아요". 복용 조건 확인(`dosage.needs_confirm`)은 `false`로 둠 | Body에서 빼고 보냄(저장 안 함) |
| `null` | 매칭이 없거나 제형을 모름 → "먹는 약이 맞나요?" | 회원이 남겨 두면 저장 |

**복용 조건**(`dosage`): AI 문서 4-3-1을 1차 범위로 줄였습니다.

| 칸 | 값 |
| --- | --- |
| `parsed_by` | `rule`(표현 사전) / `user`(회원이 고름). ERD의 `llm`은 2차입니다 |
| `needs_confirm` | 표현 사전에 없는 문장이거나, 1차에서 계산하지 않는 조건이면 `true` → "복용 조건을 확인해 주세요". 1차는 LLM으로 문장을 해석하지 않고 회원이 목록에서 고릅니다(ERD `parsed_by.llm` 2차) |
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
| `DOCUMENT_EXPIRED` | 410 | 업로드 후 3시간이 지나 원본이 삭제됨, 또는 회원이 읽기를 취소함(`DELETE /scans`). 두 경우 모두 같은 공통 문구 | "파일이 삭제됐어요. 다시 올려 주세요" |

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
  | `doc_type` | O | `prescription`(처방전) / `pill_envelope`(약봉투) |

  ```
  files: 처방전_앞.jpg, 처방전_뒤.jpg
  doc_type: prescription
  ```
- Response Body (202):

  ```json
  {
    "scan_id": 42,
    "status": "uploaded",
    "step": "reading",
    "doc_type": "prescription",
    "page_count": 2,
    "image_delete_due_at": "2026-11-20T21:30:00+09:00"
  }
  ```
- 에러: `VALIDATION_ERROR`(422) 파일 없음·`doc_type` 누락이나 잘못된 값 → 해당 칸 표시 / `FILE_TOO_LARGE`(413)·`UNSUPPORTED_FILE_TYPE`(415)·`ENCRYPTED_PDF`(422)·`INVALID_FILE`(422)·`TOO_MANY_PAGES`(422) → 올리는 단계에서 `message` 표시 후 다시 고르기 / `RATE_LIMITED`(429) OCR 호출 제한 초과 → "오늘은 더 이상 올릴 수 없어요. 직접 입력해 주세요" / `EXTERNAL_API_ERROR`는 여기서 돌려주지 않습니다(읽기 실패는 상태 조회의 `ocr_failed`로 알림)
- 비고:
  - 파일 크기·형식·암호·손상 검사는 요청을 받을 때 끝내고, 통과한 경우에만 `202`를 돌려줍니다.
  - PDF는 페이지마다 이미지로 바꿔 `document_pages`에 저장합니다. PDF 페이지는 그 파일 자리에 펼쳐서 번호를 매깁니다(예: 사진 1장 + 3쪽 PDF → 1, 2, 3, 4).
  - 이미지·PDF 모두 페이지별로 CLOVA OCR을 부릅니다(1차는 전자 PDF도 OCR). 페이지마다 10초가 넘거나 오류가 나면 최대 2회 다시 부릅니다.
  - 약 정보 정리(LLM)에 넘기기 전에 주민등록번호·환자번호·이름·면허번호·연락처를 가립니다. OCR 글자는 로그·AI 호출 기록에 남기지 않습니다(NFR-004).
  - `image_delete_due_at`은 업로드 시각 + 3시간입니다. 그때까지 확정하지 않으면 정리 작업이 원본 파일·페이지 이미지·인식 결과를 지우고 `expired`로 바꿉니다. 수정해도 연장되지 않습니다.

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
    "doc_type": "prescription",
    "image_delete_due_at": "2026-11-20T21:30:00+09:00"
  }
  ```

  인식 완료(`ocr_done`)

  ```json
  {
    "scan_id": 42,
    "status": "ocr_done",
    "step": null,
    "doc_type": "prescription",
    "image_delete_due_at": "2026-11-20T21:30:00+09:00",
    "pages": [{ "page_no": 1 }, { "page_no": 2 }],
    "masked": true,
    "prompt_version": "parse_document_v1",
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
        "is_oral": true,
        "dose_per_time": { "text": "1정", "min": 1, "max": 1, "unit": "정", "parsed": true, "confidence": 0.95, "needs_check": false },
        "times_per_day": { "value": 3, "confidence": 0.72, "needs_check": true },
        "total_days": { "value": 5, "confidence": 0.94, "needs_check": false },
        "instruction_text": "식후30분",
        "dosage": {
          "parsed_by": "rule",
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
            { "drug_id": 2210, "item_name": "가상캡슐 250mg", "company": "가상제약", "similarity": 0.81 },
            { "drug_id": 2211, "item_name": "가상캡슐 500mg", "company": "가상제약", "similarity": 0.79 }
          ]
        },
        "is_oral": null,
        "dose_per_time": { "text": "1캡슐", "min": 1, "max": 1, "unit": "캡슐", "parsed": true, "confidence": 0.9, "needs_check": false },
        "times_per_day": { "value": 2, "confidence": 0.88, "needs_check": false },
        "total_days": { "value": 5, "confidence": 0.9, "needs_check": false },
        "instruction_text": null,
        "dosage": {
          "parsed_by": "rule",
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
    "doc_type": "prescription",
    "fail_reason": "no_text",
    "message": "글자를 읽지 못했어요. 밝은 곳에서 문서 전체가 나오게 다시 찍어 주세요"
  }
  ```

  확정됨(`confirmed`) / 만료(`expired`). `medical_documents`에는 `prescription_id` 칸이 없으므로 `prescription_id`는 `prescriptions.document_id`로 찾습니다(4장 `create_prescription()` 7단계).

  ```json
  { "scan_id": 42, "status": "confirmed", "step": null, "prescription_id": 88 }
  ```
  ```json
  { "scan_id": 42, "status": "expired", "step": null }
  ```
- 에러: `NOT_FOUND`(404) 없는 문서·다른 회원의 문서 → "처방전을 찾을 수 없어요" 후 B-1로 이동
- 비고:
  - 상태별 화면과 최대 대기 시간은 6-1, 칸 모양과 노란색 표시 규칙은 6-2를 따릅니다.
  - 인식 결과를 돌려주기 전에 4장 `fill_default_meals(doses, times_per_day)`(민정)로 끼니를 미리 채웁니다. 1일 3회 + 식전·식후 3개 → `dose_no` 순으로 아침·점심·저녁, 1일 4회 + 식전·식후 3개 + 취침 전 → 같은 방식, 그 밖에는 그대로 둡니다(1일 1·2회는 `meal_unknown` 유지). `create_prescription()`과 같은 함수라 확인 화면과 저장 결과가 어긋나지 않습니다.
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
  { "doc_type": "pill_envelope" }
  ```
- Response Body (200 / 202):

  ① 200: `GET /scans/{scan_id}`의 `ocr_done` 응답과 같은 모양(`edited: true`)

  ② 202:

  ```json
  { "scan_id": 42, "status": "uploaded", "step": "structuring", "doc_type": "pill_envelope" }
  ```
- 에러: `NOT_FOUND`(404) 없는 문서·다른 회원의 문서 / `VALIDATION_ERROR`(422) 없는 `line_no`·없는 `drug_id`·1차에서 받지 않는 `timing` → `fields`의 칸 표시 / `DOCUMENT_NOT_READY`(409) 아직 읽는 중 → 로딩 화면 유지 / `DOCUMENT_ALREADY_CONFIRMED`(409) → 처방 상세로 이동 / `DOCUMENT_EXPIRED`(410) → B-1로 이동
- 비고:
  - 고친 칸은 `confidence: null`, `needs_check: false`가 됩니다. 단, 고친 용량을 표현 사전으로 읽을 수 없거나(`parsed: false`) 정·캡슐·포 0.25 미만이면 `needs_check: true`로 두어 노란색 표시를 유지합니다(용량은 필수 칸이 아니라 확정은 막지 않음). `dosage`를 고르면 `parsed_by: "user"`, `needs_confirm: false`가 됩니다.
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
        "drug_name": "가상정5mg",
        "raw_text": "가상정5mg 1 3 5 식후30분",
        "dose_per_time": { "text": "1정", "min": 1, "max": 1, "unit": "정", "parsed": true },
        "times_per_day": 3,
        "total_days": 5,
        "instruction_text": "식후30분",
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
      },
      {
        "line_no": 2,
        "drug_id": 2210,
        "drug_name": "가상캡슐",
        "raw_text": "가상캡슐 1 2 5",
        "dose_per_time": { "text": "1캡슐", "min": 1, "max": 1, "unit": "캡슐", "parsed": true },
        "times_per_day": 2,
        "total_days": 5,
        "instruction_text": null,
        "dosage": {
          "parsed_by": "rule",
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
  | `drugs[].drug_name` | 빈칸 불가. 처방전에 적힌 약품명(회원이 고쳤으면 고친 이름)이며 `prescription_items.drug_name_raw`로 저장됩니다. 화면에 보일 약 이름은 `drug_id`로 `drugs.item_name`을 읽습니다. 공공데이터에 없는 약은 `drug_id: null`로 이름만 저장 가능 |
  | `drugs[].raw_text` | 선택. 처방전 원문 줄(가린 값)이며 `prescription_items.source_text`로 저장됩니다. 회원이 새로 추가한 줄은 `null` |
  | `drugs[].drug_id` | `drugs.is_oral = false`인 약은 받지 않습니다(먹는 약만 등록) |
  | `drugs[].dose_per_time.text` | 빈칸 불가(`parsed: false`도 저장 가능) |
  | `drugs[].times_per_day` | 1~4의 정수(ERD). `as_needed: true`면 `null` 가능 |
  | `drugs[].total_days` | 1~365의 정수(ERD) |
  | `drugs[].dosage.cycle.type`, `start_date` | 1차는 `daily`만 |
  | `drugs[].dosage.doses[].timing` | `after_meal` / `before_meal` / `bedtime` / `null`. `null`이거나 식전·식후인데 `meal`이 `null`이면 '복용 조건 확인 필요'로 저장됩니다 |
- Response Body (201):

  ```json
  {
    "scan_id": 42,
    "status": "confirmed",
    "prescription_id": 88,
    "conditions_to_confirm": [
      { "condition_id": 5014, "prescription_item_id": 502, "drug_name": "가상캡슐 250mg", "dose_no": 1, "reason": "timing_unknown" },
      { "condition_id": 5015, "prescription_item_id": 502, "drug_name": "가상캡슐 250mg", "dose_no": 2, "reason": "timing_unknown" }
    ]
  }
  ```
  `reason`은 회차마다 하나입니다.

  | `reason` | 언제 | 화면 |
  | --- | --- | --- |
  | `timing_unknown` | `timing`이 `null` (식전·식후·취침 전을 모름. 끼니도 모르는 경우 포함) | 식전·식후·취침 전과 끼니를 모두 고르게 함 |
  | `meal_unknown` | `timing`은 식전·식후인데 `meal`이 `null` | 끼니만 고르게 함 |

  예: "1일 2회 복용"만 적힌 약은 두 회차 모두 `timing_unknown`입니다.
- 에러: `VALIDATION_ERROR`(422) 필수 칸 빈칸·잘못된 값 → [저장하기]를 막고 `fields`의 칸을 표시 / `NOT_FOUND`(404) 없는 문서·다른 회원의 문서 / `DOCUMENT_NOT_READY`(409) 아직 읽는 중·읽기 실패 / `DOCUMENT_ALREADY_CONFIRMED`(409) 이미 확정 → `GET /scans/{scan_id}`의 `prescription_id`로 처방 상세 이동 / `DOCUMENT_EXPIRED`(410) → "파일이 삭제됐어요. 다시 올려 주세요"

  ```json
  {
    "code": "VALIDATION_ERROR",
    "message": "빈칸을 채워 주세요",
    "fields": { "drugs[1].total_days": "총 일수를 입력해 주세요" }
  }
  ```
- 비고:
  - 처리 순서
    1. 문서 행을 잠그고 상태·소유를 확인합니다(`ocr_done`이 아니면 위 에러).
    2. `create_prescription(db, user_id, data, source="ocr", background_tasks=..., medical_document_id=42)`를 부릅니다(4장). 필수 칸 검사, 처방·시간표·복용 기록 저장, 문서 `confirmed`·`parsed_result = NULL` 처리, 가이드 행 생성이 이 함수 안에서 한 트랜잭션으로 끝납니다. 검사 실패(`PrescriptionValidationError`)는 `VALIDATION_ERROR`로 바꿔 돌려줍니다.
    3. 이 API가 커밋합니다(4장: 커밋은 부른 API).
    4. 커밋 뒤에 원본 파일·페이지 이미지를 지웁니다. 파일 삭제는 트랜잭션으로 되돌릴 수 없어서 커밋 뒤에 합니다.
    5. `create_prescription()`이 돌려준 `prescription_id`, `conditions_to_confirm`을 그대로 응답합니다.
  - 4 삭제에 실패해도 응답은 성공으로 돌려주고, 정리 작업이 다시 지웁니다. 2가 실패하면 트랜잭션이 모두 되돌려져 상태는 `ocr_done`으로 남고 원본도 지우지 않으므로 회원이 다시 [저장하기]를 누를 수 있습니다.
  - 같은 요청이 두 번 들어와도 처방이 두 번 생기지 않도록 문서 행을 잠그고 상태를 확인합니다.
  - `conditions_to_confirm`이 비어 있지 않으면 B-2에서 이어서 복용 조건을 고르게 하고(`PATCH /dose-conditions/{condition_id}`), 비어 있으면 홈으로 이동합니다(REQ-OCR-004). 1일 3회인데 끼니가 안 적힌 경우는 4장 시간표 규칙대로 아침·점심·저녁으로 채워지므로 이 목록에 들어가지 않습니다.
  - 복용 기록은 확정 시각 이후 회차부터 만듭니다(4장 합의). 한 약에서 회차 하나라도 확인이 필요하면 그 약은 복용 기록을 만들지 않고, 모두 고른 뒤 `recalculate_schedule()`이 만듭니다.
  - `drug_id: null`인 약은 가이드에서 "이 약은 안내 정보가 없어요"로 나갑니다(VERI-003 1차 범위).
  - ERD에는 1회 용량 중 `dose_text`만 저장합니다. Body의 `min`·`max`·`parsed`는 저장하지 않고, 조회할 때 `parse_dose_text()`(6-4)로 다시 만듭니다. 그래서 같은 `text`면 저장 전후 값이 같습니다.

### [DELETE] /api/v1/scans/{scan_id}
- 설명: 읽는 중 화면의 [취소]. 읽기 작업을 멈추고 원본 파일·페이지 이미지·인식 결과를 바로 지웁니다.
- 인증: 필요
- 관련 요구사항: REQ-OCR-002, REQ-NFR-004
- 관련 화면: B-1-2 읽는 중([취소]), B-2 인식 결과 확인(저장하지 않고 나가기)
- 관련 테이블: `medical_documents`, `document_pages`
- Path / Query: Path `scan_id`(`medical_documents.id`)
- Request Body: 없음
- Response Body (204): 본문 없음
- 에러: `NOT_FOUND`(404) 없는 문서·다른 회원의 문서 / `DOCUMENT_ALREADY_CONFIRMED`(409) 이미 확정한 문서 → 홈으로 이동
- 비고:
  - `uploaded`·`ocr_done`·`ocr_failed` 상태에서 받습니다. 이미 `expired`면 아무것도 하지 않고 204를 돌려줍니다(여러 번 눌러도 같음).
  - 문서 행은 지우지 않고 `status = expired`, `parsed_result = NULL`로 바꾼 뒤 원본 파일·페이지 이미지를 지웁니다. 행을 남겨 회원당 하루 OCR 호출 수(20회)에 그대로 셉니다.
  - 읽기 작업이 아직 돌고 있으면, 작업은 결과를 저장하기 전에 문서 상태를 다시 읽어 `expired`면 결과를 버리고 끝냅니다. 이미 보낸 CLOVA OCR·LLM 호출은 되돌릴 수 없습니다.
  - 파일 삭제는 커밋 뒤에 합니다. 삭제에 실패해도 204를 돌려주고 정리 작업이 다시 지웁니다(확정 API 비고와 같음). 그래서 정리 작업은 3시간이 지난 문서뿐 아니라 `status`가 `confirmed`·`expired`인데 `document_pages.deleted_at`이 비어 있는(파일이 남은) 페이지도 골라 지웁니다.
  - 취소한 문서를 다시 열면 `expired` 화면(6-1)과 `DOCUMENT_EXPIRED`가 나옵니다. 3시간 만료와 취소에 모두 맞도록 문구를 "파일이 삭제됐어요. 다시 올려 주세요"로 통일했습니다(11/23 채민님 리뷰).

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
      { "drug_id": 1203, "item_name": "가상정 5mg", "ingredient_name": "가상성분", "company": "가상제약", "is_oral": true, "has_public_data": true, "matched_by": "exact", "similarity": 1.0 },
      { "drug_id": 1204, "item_name": "가상정 10mg", "ingredient_name": "가상성분", "company": "가상제약", "is_oral": true, "has_public_data": true, "matched_by": "prefix", "similarity": 0.86 }
    ]
  }
  ```
- 에러: `VALIDATION_ERROR`(422) `q`가 비었거나 50자 초과, `limit` 범위 밖 → 프론트에서 먼저 막음
- 비고:
  - 자동완성이라 1번 목록 규칙(`page`·`size`·`total`)을 쓰지 않습니다(1번 '목록' 규칙의 예외로 적힘).
  - 검색 전에 공백·괄호를 지우고 단위 표기를 맞춰 비교합니다(예: "가상정 5mg"·"가상정5mg"·"가상정5밀리그램"은 같음). 공공데이터 품목명은 "mg"를 "밀리그램"(또는 "밀리그람")으로 적는 경우가 많기 때문입니다.
  - 정렬: 정확 일치(`exact`) → 앞부분 일치(`prefix`) → 이름 유사도(`similar`, pg_trgm) 순입니다. 유사도 기준은 0.3에서 시작해 가상 처방전 테스트 후 조정합니다.
  - 결과가 없으면 `{"items": []}`를 돌려줍니다. 화면에는 "검색 결과가 없어요. 약 이름 그대로 저장할 수도 있어요"를 띄웁니다.
  - OCR 약품 매칭은 HTTP를 거치지 않고 같은 검색 함수를 서버 안에서 부릅니다. 정확 일치가 1개면 `exact`, 아니면 기준 이상 상위 3개를 `candidates`, 없으면 `none`입니다.
  - 응답 칸 이름은 ERD `drugs` 컬럼(`item_name`, `ingredient_name`, `company`)을 그대로 씁니다(4장 4-9 #20). `GET /scans`의 매칭 후보(`candidates[]`)도 같은 이름입니다. 확정 Body의 `drug_name`은 고른 약의 `item_name`이 아니라 처방전에 적힌 이름입니다. 약 상세는 5장 `GET /prescription-items/{prescription_item_id}`를 씁니다.
  - 입력할 때마다 부르지 않도록 프론트에서 300ms 디바운스를 부탁드립니다.

### [PATCH] /api/v1/dose-conditions/{condition_id}
- 설명: 처방 확정 뒤에도 '복용 조건 확인 필요'로 남은 회차의 복용 조건을 회원이 골라 저장합니다. 확인 화면(B-2)과 홈의 끼니 고르기(A-2)가 함께 씁니다. 보낸 칸만 바꾸는 부분 수정이며, 저장하면 그 회차의 복용 시각과 앞으로의 복용 기록을 다시 계산합니다.
- 인증: 필요
- 관련 요구사항: REQ-MED-008
- 관련 화면: B-2 인식 결과 확인(확정 직후 이어서 고르기), A-2 홈('복용 시간 확인 필요'의 아침·점심·저녁 버튼), C-2 약 상세('복용 조건 확인 필요' 약의 회차별 고르기, 홈 `timing_unknown` 카드에서 진입, 11/23 채민·설아)
- 관련 테이블: `dose_conditions`, `dose_schedules`, `intake_logs`
- Path / Query: Path `condition_id`(`dose_conditions.id`, 약 한 줄의 회차 하나)
- Request Body: 바꿀 칸만 보냅니다. 보내지 않은 칸은 저장된 값을 그대로 둡니다.

  B-2에서 모두 고를 때(`timing_unknown`)

  ```json
  { "meal": "breakfast", "timing": "after_meal", "offset_min": 30 }
  ```

  홈에서 끼니만 고를 때(`meal_unknown`)

  ```json
  { "meal": "breakfast" }
  ```

  | 칸 | 규칙 |
  | --- | --- |
  | `timing` | `after_meal`(식후 n분) / `before_meal`(식전 n분) / `bedtime`(취침 전) |
  | `meal` | `breakfast` / `lunch` / `dinner`. 취침 전이면 `null` |
  | `offset_min` | 식전·식후 몇 분(0~120). 취침 전이면 `null` |

  합친 결과(저장된 값 + 보낸 칸)가 아래를 모두 채우면 확인이 끝나고(`needs_confirm: false`), 아니면 '확인 필요'로 남습니다.
  - 식전·식후: `meal`, `offset_min` 모두 있음
  - 취침 전: `meal`·`offset_min` 없음
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
  `remaining_to_confirm`은 같은 처방에서 아직 확인이 필요한 회차 수입니다. `0`이 되면 B-2·홈에서는 홈으로 이동하고, C-2에서는 약 상세를 새로고침합니다.
  홈에서 끼니만 골랐는데 `timing`도 비어 있으면 `needs_confirm: true`, `dose_time: null`로 돌아옵니다. 이때는 "식전·식후도 골라 주세요"와 함께 그 약의 약 상세(C-2)로 보내 주세요.
- 에러: `NOT_FOUND`(404) 없는 조건·다른 회원의 조건 / `VALIDATION_ERROR`(422) 칸 값이 위 목록에 없음, 빈 Body → 해당 칸 표시
- 비고:
  - 1차에 고를 수 있는 조건은 직접 입력(MED-001)과 같습니다. 식간·공복·n시간 간격은 2차입니다.
  - '필요시'는 약 단위 조건이라 이 API로 바꾸지 않습니다. 1차에는 확정 전에 B-2에서 고릅니다.
  - 이미 확인이 끝난 조건도 다시 고칠 수 있습니다.
  - 저장 후 4장 `recalculate_schedule(db, prescription_item_id)`를 부르고, 조건 변경과 함께 이 API가 커밋합니다. 지금 이후의 `pending` 기록만 바꾸고 `taken`·`missed`는 그대로 둡니다. 응답의 `dose_time`·`remaining_to_confirm`은 이 함수가 돌려준 값입니다.
  - 같은 약의 다른 회차가 아직 확인 필요면 `dose_time`은 계산되지만 복용 기록은 아직 만들지 않습니다(4장 규칙). 마지막 회차를 고르면 그때 만들어집니다.
  - 1일 2회처럼 회차가 여러 개면 회차마다 따로 부릅니다. 화면에서 "아침·저녁" 버튼 하나로 보여 줘도 프론트가 회차별로 호출합니다.
  - `dose_time`은 그 함수가 계산한 값을 그대로 돌려줍니다. 가이드는 조회할 때 시간표 값으로 시각을 채우므로(7-1) 따로 맞출 필요가 없습니다.

### [내부] verify_guide()
- 설명: AI B가 만든 가이드 하나를 규칙으로 검사해 통과 여부와 틀린 문장을 돌려줍니다. 복약 가이드와 생활습관 가이드를 같은 함수로 검사하고, `kind`에 따라 검사 규칙만 달라집니다. LLM을 부르지 않습니다.
- 인증: 해당 없음(서버 안에서 호출)
- 관련 요구사항: REQ-VERI-001, REQ-VERI-002, REQ-VERI-003(1차 최소 범위), REQ-VERI-004, REQ-VERI-005
- 관련 화면: D-2 가이드 보기('확인 필요' 표시)
- 관련 테이블: `drugs`(공공데이터 여부 조회). 검증 결과 저장(`guide_attempts`)은 2차이며, 1차는 서버 로그에만 남깁니다
- 호출하는 곳: 7-7 `run_guide_generation(guide_id)`의 5단계(`status = verifying`). 복약·생활습관 가이드마다 한 번씩 부릅니다
- 입력:

  ```python
  def verify_guide(
      guide: dict,                       # 7-1 content (복약 또는 생활습관 가이드 1개)
      prescription: dict,                # get_confirmed_prescription() 반환값
      *,
      guide_id: int,                     # guides.id (실패해도 행이 남으므로 이 ID를 씀)
      kind: str = "medication",          # "medication" / "lifestyle"
      user_conditions: list[str] | None = None,  # 건강 프로필의 기저질환 (VERI-004 ⓒ 질환 단정 검사)
  ) -> dict: ...
  ```
- 출력:

  복약 가이드(`kind="medication"`)

  ```json
  {
    "guide_id": 9001,
    "kind": "medication",
    "passed": false,
    "fail_reasons": [
      { "type": "forbidden", "drug_name": "가상캡슐", "prescription_item_id": 502, "item_id": "d1-h1", "detail": "복용 중단 권유 표현" }
    ],
    "item_checks": { "d1-h1": "fallback" },
    "rules_version": "verify_rules_v1",
    "duration_ms": 180,
    "checked_at": "2026-11-20T18:30:05+09:00"
  }
  ```

  생활습관 가이드(`kind="lifestyle"`)

  ```json
  {
    "guide_id": 9002,
    "kind": "lifestyle",
    "passed": false,
    "fail_reasons": [
      { "type": "forbidden", "drug_name": null, "prescription_item_id": null, "item_id": "l-e1", "detail": "복용 변경 권유 표현" }
    ],
    "item_checks": { "l-e1": "fallback" },
    "rules_version": "verify_rules_v1",
    "duration_ms": 60,
    "checked_at": "2026-11-20T18:30:05+09:00"
  }
  ```

  | 칸 | 설명 |
  | --- | --- |
  | `passed` | 틀린 곳이 하나도 없으면 `true` → `completed` |
  | `fail_reasons[]` | `{type, drug_name, prescription_item_id, item_id, detail}`. 생활습관은 약에 속하지 않아 `drug_name`·`prescription_item_id`가 `null`. 약 단위 실패(아래 표의 `item_id`가 없는 실패)는 `item_id: null` |
  | `item_checks` | 틀린 문장(`item_id`)마다 `"fallback"`. 가이드 생성 쪽이 7-1 비고 표대로 문장을 바꾸거나(복약) 빼고(생활습관) `check` 칸에 넣습니다 |
- 검사 규칙(1차, AI 문서 11-2):

  | 규칙 | 복약 | 생활습관 | 무엇을 | 실패 `type` |
  | --- | --- | --- | --- | --- |
  | VERI-001 원문 대조 | O | X | `dose_per_time`·`times_per_day`·`total_days`·`easy_text`가 확정 처방과 같은지(`prescription_item_id`로 짝지음). 코드 틀로 채우므로 코드가 맞게 복사했는지 보는 안전망입니다 | `value_mismatch`, `text_number_mismatch`, `missing_value` |
  | VERI-002 빠진 약 | O | X | 가이드 `drugs[]`의 `prescription_item_id`가 처방과 같은지 | `missing_drug` |
  | VERI-003 1차 | O | X | `has_public_data`를 약품 DB로 다시 판정. `false`인 약에 주의사항·부작용·병원 방문 문장이 있으면 실패 | `no_source` |
  | VERI-004 금지 표현 | O | O | LLM이 쓴 문장에서 ⓐ 복용 중단·용량 변경·약 대체 권유 ⓑ 처방에 없는 약·건강기능식품 이름 ⓒ `user_conditions`에 없는 질환을 가진 것처럼 단정하는 표현 ⓓ 약의 용량·횟수 숫자(숫자는 코드 틀만 씀). 공공데이터 원문 인용·병원 방문 고정 문구는 예외 | `forbidden`, `unknown_drug` |

  - `dose_times`는 7-1에서 조회할 때 시간표 값으로 채우므로 검사하지 않습니다.
  - "하루 30분 걷기"처럼 약과 상관없는 숫자는 ⓓ에 걸리지 않습니다.
- 에러: 규칙 위반은 예외를 던지지 않고 `passed: false`로 돌려줍니다. 가이드 JSON 모양이 깨졌으면 `missing_value`로 돌려줍니다. 함수 내부 오류만 예외(`VerifyError`)를 던지며, 이때 가이드 생성 쪽은 `failed`로 처리합니다.
- 비고:
  - 1차는 다시 쓰기가 없어서(1차 축소안) 검사는 가이드마다 한 번뿐이고, 틀린 문장에는 항상 `fallback`을 표시합니다. 그래서 `attempt_no`·`is_last_attempt` 입력은 두지 않습니다. 7-7 검증 호출에서도 두 인자를 빼 주세요 → 유정님 확인. 다시 쓰기는 2차에 `attempt_no`와 함께 추가합니다.
  - 약 단위 실패(`value_mismatch`·`text_number_mismatch`·`missing_value`·`missing_drug`)는 코드 틀 때문에 생기지 않아야 합니다. 생기면 7-7 합의대로 코드 오류로 기록하고 그 가이드를 `failed`로 처리합니다. 그래서 약 단위 대체 칸(`fallback_drug_ids`)은 두지 않습니다.
  - 문장을 무엇으로 바꾸는지는 7-1 비고 표를 따릅니다. 검증 함수는 표시만 하고 글은 바꾸지 않습니다.
  - 칸 이름은 7장에 맞췄습니다(AI 문서 4-2의 `prescription_drug_id` → `prescription_item_id`, `guide_job_id` → `guide_id`). 근거 출처 대조(VERI-003 2차)는 7장 출처의 `drug_id`(약 근거)·`rag_document_id`(생활습관·질환 자료 근거)를 씁니다.
  - 목표 시간: 1건 1초(내부 목표), 5초 이내(NFR-014). 7-7의 30초 안에 검사 시간이 포함되므로 `duration_ms`를 꼭 채웁니다.
  - 1차 측정용으로 가이드마다 검사 시간·실패 종류·프롬프트 버전(`guide_medication_v1` / `guide_lifestyle_v1`)을 서버 로그에 남깁니다.
  - 금지 표현·약 이름 목록은 `check_full()`(6-4)과 같은 규칙 파일(`verify_rules_v1`)을 씁니다.

### 6-4. 다른 파트가 부르는 AI A 함수

API는 아니지만 다른 섹션이 부르는 함수입니다. 입력·출력만 적고, 세부 규칙은 구현하면서 이 표를 고칩니다.

| 함수 | 부르는 곳 | 입력 → 출력 | 1차 범위 |
| --- | --- | --- | --- |
| `parse_dose_text(text)` | 6장 `PATCH /scans`·확정 API, 5장 `get_confirmed_prescription()`(설아) | `"1/2정"` → `{"text": "1/2정", "min": 0.5, "max": 0.5, "unit": "정", "parsed": true}` | 표현 사전(`dosage_dict_v1`)만 씁니다. ERD에는 `dose_text`만 저장되므로 조회할 때 이 함수로 다시 만듭니다(7-7 비고). 같은 글자면 항상 같은 결과입니다. 읽을 수 없으면 `min`·`max`·`unit`이 `null`, `parsed: false` |
| `mask_text(text)` | 6장 OCR 글자(LLM에 넘기기 전), 7-6 챗봇 질문(저장 전) | 글자 → 가린 글자(`[주민번호]`, `[연락처]`, `[이메일]`, `[환자번호]`, `[면허번호]`) | 규칙(정규식)으로 가립니다. 이름은 처방전의 '성명' 칸처럼 위치로 알 수 있을 때만 `[이름]`으로 가리고, 챗봇 질문 속 이름은 1차에 가리지 않습니다 |
| `check_full(answer, *, question, current_drugs, user_conditions=None)` | 7-6 ⑥ 챗봇 답변이 끝난 뒤 | 답변 전체 + 가린 질문 + 복용 중인 약 이름 → `{"passed": false, "types": ["forbidden"], "rules_version": "verify_rules_v1"}` | VERI-004 ⓐⓑⓒ 검사. 질문에 나온 약은 처방에 없어도 실패로 보지 않습니다. 결과는 **기록만** 하고 화면에는 보내지 않습니다(정정 안내는 2차 VERI-007). 저장은 `chat_messages.check_result`(jsonb)에 반환값을 그대로 넣습니다(E11, 11/23 확정). 통과는 `{"passed": true, "types": [], "rules_version": "verify_rules_v1"}`, 검사를 하지 않았거나 오류가 나면 `null`, 회원 질문 행은 항상 `null`입니다. `verify_status`는 정정 안내(VERI-007)를 넣는 2차에 다시 정합니다. 답변 문장은 결과에 다시 담지 않습니다. 오류가 나도 호출하는 쪽은 답변을 막지 않습니다 |

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
| ✅ 숫자(용량·횟수·일수·복용 시각)와 약 목록 틀, `easy_text`(먹는 법 문장)는 확정 처방에서 **코드 틀로 채웁니다.** LLM은 주의할 점·부작용·병원에 가야 할 증상과 생활습관 설명만 씁니다. 그래서 약 단위 실패(숫자 불일치·빠진 약)는 생기지 않아야 하며, `verify_guide()`의 `fallback_drug_ids`는 쓰지 않습니다(11/20 채민님과 합의) | 채민 |
| 복용 시각: 1차는 기본 일과로 계산한 `dose_schedules`(weekday 한 행)를 그대로 씁니다. `needs_check`인 회차는 시각을 비우고 "복용 시간 확인 필요"로 둡니다(백엔드 전달사항 3-3은 생활 일과가 2차로 내려가 1차에서는 해당 없음) | 민정 · 설아 |
| **SSE 이벤트는 이 섹션(7-6)을 기준으로 해 주세요.** (민정님이 1-3 표를 고치기로 함, 11/20) 1-3 표는 백엔드 합의(전달사항 2-4) 전 이름이라 수정이 필요합니다: `token` → `delta`, `message` → `text`, 응급 `type`은 `physical` / `self_harm` + `call`(`119` / `109`), `done`은 API가 보냄 | 설아 · 민정 |
| ✅ 생활습관 가이드도 같은 `verify_guide()`를 `kind="lifestyle"`로 부르고, 금지 표현(VERI-004)만 검사합니다. 질환 단정 검사를 위해 기저질환(`user_conditions`)을 함께 넘깁니다. 걸린 항목은 대신할 기본 정보가 없어 **빼고** 보여 줍니다(11/20 채민님과 합의) | 채민 |
| ✅ 챗봇 금지 표현(VERI-004) 1차: 시스템 프롬프트로 막고, 답변이 끝난 뒤 `check_full()`(채민)로 검사해 **결과는 기록만** 합니다. 검사 오류가 나도 답변은 막지 않습니다. 화면 정정 안내(`correction` 이벤트)는 2차(VERI-007)입니다 | 채민 |
| 챗봇 검사 결과는 `chat_messages.check_result`(jsonb)에 저장합니다. 민정님이 ERD에 추가 제안(11/20) | 민정 · 채민 |
| 챗봇 질문은 저장 전에 개인정보 가리기 함수(`mask_text()`, 채민)를 거칩니다. 3-1 표 담당 추가는 민정님 PR에서 반영 | 채민 · 민정 |
| 이전 대화 목록·내용 조회는 2차(CHAT-003)입니다. 1차는 채팅창을 열 때마다 대화방을 만들고 목록은 숨깁니다(AI 문서 D23) | 설아 |
| 공공데이터 `drugs` 적재를 RAG 수집과 같은 파이프라인에서 처리합니다. 컬럼은 ERD `drugs`를 따르고, 데이터 기준일(`data_fetched_at`)을 함께 저장합니다 | 민정 · 채민(약품 매칭) |
| ✅ 근거 검색의 벡터 DB는 PostgreSQL pgvector를 씁니다(11/23 공지). 문서 조각·임베딩 테이블과 임베딩 모델은 유정이 ERD에 추가합니다(11/27까지) | 민정 · 설아 |
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
              { "item_id": "d1-c1", "text": "…", "sources": [{ "drug_id": 1203, "name": "의약품개요정보(e약은요): 가상캡슐" }], "check": null }
            ],
            "side_effects": [
              { "item_id": "d1-s1", "symptom": "…", "what_to_do": "…", "sources": [{ "drug_id": 1203, "name": "의약품개요정보(e약은요): 가상캡슐" }], "check": null }
            ],
            "see_doctor_if": [
              { "item_id": "d1-h1", "text": "…", "sources": [{ "drug_id": 1203, "name": "의약품개요정보(e약은요): 가상캡슐" }], "check": "fallback" }
            ]
          }
        ],
        "sources": [{ "drug_id": 1203, "name": "의약품개요정보(e약은요): 가상캡슐", "data_fetched_at": "2026-11-20" }]
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
    | `failed` | `fallback`의 약 기본 정보 + "가이드 생성이 지연되고 있어요. 잠시 후 다시 시도해 주세요" + [다시 시도](REQ-GUIDE-007 문구, 11/23) |
  - 화면은 두 가이드가 모두 `completed`, `completed_with_replacements`, `failed` 중 하나가 되면 폴링을 멈춥니다.
  - 30초 시간 초과는 두 곳에서 처리합니다. ① 백그라운드 작업이 30초 안에 끝나지 않으면 스스로 `failed`로 바꿉니다. ② 서버가 생성 중에 재시작되면 행이 `generating`·`verifying`에 남으므로, 이 API를 부를 때 상태가 `generating`·`verifying`이고 `updated_at`이 30초보다 오래됐으면 **그 자리에서 `failed`로 바꿔** 내려줍니다(민정님 제안).
  - 가이드 행이 아예 없으면(행을 만들기 전에 실패) `medication`·`lifestyle`을 모두 `failed`(`guide_id: null`)로 내려주고, 7-2 [다시 시도]가 행을 새로 만듭니다. 1차는 `create_prescription()` 트랜잭션 안에서 행을 만들기 때문에 처방이 있으면 행도 있는 게 정상입니다.
  - 만드는 중·실패 응답에도 `is_outdated`, `used_default_profile`, `disclaimer` 키를 항상 넣습니다(값이 없으면 `null`). 프론트 응답 타입을 하나로 쓰기 위함입니다.
  - 용량·횟수·일수·복용 시각은 확정 처방(`get_confirmed_prescription()`)에서 그대로 복사합니다. LLM이 만들지 않습니다.
  - `how_to_take` 전체(`dose_per_time`, `times_per_day`, `total_days`, `dose_times`, `easy_text`)는 **조회할 때** `get_confirmed_prescription()`(5장) 값으로 채웁니다. 확정 후 복용 조건을 바꿔도(`PATCH /dose-conditions`) 가이드와 처방이 어긋나지 않게 하기 위함입니다(6장 채민님 제안, 11/23 설아 확장). 모두 코드 틀로 만드는 칸이라 LLM을 다시 부르지 않습니다. 필요시 약과 `needs_check` 회차의 `dose_times`는 빈 목록입니다.
  - `has_public_data: false`(약품 매칭 실패)인 약은 복용 방법만 보여 주고 "이 약은 안내 정보가 없어요"를 표시합니다.
  - `check`는 1차에 `null`(표시 없음)과 `fallback`(확인 필요)만 씁니다. '출처 확인됨'(`verified`)은 2차(VERI-006)입니다.
  - `fallback` 항목은 표시만 하지 않고 **문장을 바꿔서** 내려줍니다. 금지 표현이 나온 문장이 그대로 보이지 않게 하기 위함입니다.

    | 칸 | 바꿀 문장 |
    | --- | --- |
    | `cautions`(주의할 점) | 그 약의 공공데이터 주의사항 원문(`drugs.precautions`) |
    | `side_effects`(부작용·대처) | 그 약의 공공데이터 부작용 원문(`drugs.side_effects`), `what_to_do`는 "증상이 계속되면 의사·약사에게 알려 주세요" |
    | `see_doctor_if`(병원에 가야 할 증상) | 고정 문구 "이 부분은 의사·약사에게 확인해 주세요"(e약은요에 맞는 칸이 없음) |
    | 생활습관 항목 | 바꾸지 않고 항목을 뺍니다 |

    공공데이터 원문이 비어 있으면 고정 문구를 씁니다. `easy_text`(먹는 법)는 코드 틀로 만들어 `fallback` 대상이 아닙니다.
  - `used_default_profile: true`이면 상단에 "건강 프로필을 입력하면 더 정확한 안내를 받을 수 있어요"를 표시합니다(GUIDE-002). 기준은 가이드를 만들 때 `health_profiles` 행이 있었는지입니다(4장 `is_registered`와 같음). 가이드를 만든 뒤에 건강 프로필을 입력했으면(`GET /users/me/health-profile`의 `is_registered: true`) 이 문구 대신 "입력한 건강 프로필은 다음 처방 가이드부터 반영돼요"를 표시합니다. 1차는 다시 만들기가 없어서 이미 만든 가이드는 바꾸지 않습니다(GUIDE-005 2차, 4장 `PUT /users/me/health-profile` 비고와 같음) (문구 ✅ 11/23 설아, 와이어프레임 D-2 반영)
  - `content.sources`는 화면 하단 출처 목록입니다. 문장별 출처에서 겹치는 것을 뺀 목록이고, 실제로 문장에 쓴 근거만 넣습니다(GUIDE-003).
  - 출처 하나는 `{"drug_id" 또는 "rag_document_id", "name"}`입니다. 약 설명(e약은요·허가정보) 근거는 `drugs`를 바로 읽으므로 `drug_id`, 생활습관·질환 관리 자료 근거는 `rag_documents`의 `rag_document_id`를 씁니다(ERD `rag_documents`·`rag_chunks`, 11/26). ERD `guides.content` 노트("근거(drug_id 또는 rag_document_id)")와 같습니다. 
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
  - 다시 시도할 때 `status = generating`과 함께 `updated_at`을 지금 시각으로 바꿔, 30초를 새로 셉니다. 가이드 행이 없으면 새로 만듭니다.
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
  - 직접 입력한 처방은 `prescribed_date`가 `null`입니다. 이때 화면은 등록일을 "○월 ○일 등록"으로 보여 줍니다(11/23 설아님 결정, 4장과 같음).
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
  - '복용 중인 약'은 민정님 공용 함수로 고르고, 기준은 5-0 '복용 중'(시작일과 상관없이 종료일이 오늘 이후)입니다(11/23 유정님 리뷰). 7-6 프롬프트, 설아님 처방 목록과 같은 기준입니다.
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
  | 3 | `sources` | AI | 답변이 끝났을 때 | `{"items": [{"drug_id": 1204, "name": "의약품개요정보(e약은요): 가상정"}]}`. 약 근거는 `drug_id`, 생활습관·질환 자료 근거는 `rag_document_id` |
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
  data: {"items": [{"drug_id": 1204, "name": "의약품개요정보(e약은요): 가상정"}]}

  event: done
  data: {"message_id": 812, "show_profile_link": false}
  ```
- 에러: SSE를 열기 전에 막는 것 → `VALIDATION_ERROR`(422) 빈 질문·500자 초과 → 화면에서 먼저 막고(전송 버튼 비활성, 500자 넘게 입력 안 됨) 혹시 오면 "질문은 500자까지 입력할 수 있어요" / `NOT_FOUND`(404) 없는 대화방·다른 회원의 대화방 → 7-5로 새 대화방 만들기 / `ANSWER_IN_PROGRESS`(409) 앞 질문의 답변이 아직 나오는 중 → 전송 버튼 비활성. SSE 도중 실패는 `error` 이벤트로 보냅니다.
- 비고:
  - 처리 순서: ① 질문 가리기(`mask_text()`) 후 저장 → `meta` ② 응급 표현 확인(규칙, LLM 호출 전) ③ 범위 확인(1차는 키워드, 범위 밖이면 고정 문구, LLM 안 부름) ④ 근거 검색(복용 중인 약 + 질문에 나온 약) ⑤ LLM 답변(`delta`) ⑥ 금지 표현 검사(`check_full()`, 1차는 기록만) ⑦ `sources` ⑧ 답변 저장 → `done`
  - 프롬프트에는 복용 중인 약(이름·성분명·복용법 요약·복용 시각), 건강 프로필(이름·이메일 제외, 나이는 나이대로), 최근 10턴을 넣습니다(CHAT-002). 복용 중인 약은 민정님 공용 함수로 고르고, 건강 프로필 필드 이름은 4장 응답 이름을 그대로 씁니다.
  - POST + `Authorization` 헤더를 쓰므로 프론트는 `EventSource` 대신 `fetch` 스트림으로 받습니다(설아님 참고). 배포 때 Nginx 응답 버퍼링 끄기는 민정님이 챙깁니다. Vercel rewrites(4-1)를 거쳐도 스트림이 끊기지 않고 조금씩 오는지 첫 배포 때 확인하고, 한 번에 몰려오거나 끊기면 4-1 Plan B로 바꿉니다.
  - 서버가 답변 중에 재시작되면 답변 메시지가 `streaming`에 남아 대화방이 막힙니다. 그래서 `ANSWER_IN_PROGRESS`는 `streaming` 메시지가 **60초 안에** 만들어졌을 때만 돌려주고, 60초가 지난 `streaming`은 `failed`로 바꾼 뒤 새 질문을 받습니다.
  - 건강 프로필이 없으면 약 정보만으로 답하고, 대화방에서 처음 한 번만 `show_profile_link: true`를 보냅니다.
  - 신체 응급(`physical`)은 빨간 카드로 119 안내를 먼저 보여 주고 이어서 답변합니다. 자해·자살(`self_harm`)은 109 안내만 보여 주고 일반 답변을 하지 않습니다(CHAT-004).
  - 범위 밖 안내는 LLM을 쓰지 않는 고정 문구입니다. '진료 준비에 추가' 버튼은 2차(MED-015)에 붙입니다.
  - 회원이 중간에 연결을 끊으면 API가 AI 생성을 닫고, AI는 LLM 호출도 함께 멈춥니다(비용).
  - ERD 저장 값: `physical` → `message_type: emergency_physical`, `self_harm` → `emergency_self_harm`, `out_of_scope` → `out_of_scope`, `error` → `status: failed`.
  - 하루 50개 제한(`RATE_LIMITED`)과 차감 규칙은 2차(CHAT-006)입니다.

### 7-7. 내부 함수: `start_guide_generation(db, prescription_id, background_tasks)`
- 설명: 확정된 처방으로 복약 가이드와 생활습관 가이드를 따로, 동시에 만들기 시작합니다. 바로 돌아오고, 실제 생성은 백그라운드에서 합니다.
- 부르는 곳: 민정님 `create_prescription()`의 마지막 단계(사진 확정·직접 입력 공통)
- 관련 요구사항: REQ-GUIDE-001·002·003·006·007, REQ-VERI-005, REQ-NFR-006
- 관련 테이블: `guides`, `prompt_versions`, `llm_call_logs`, `rag_documents`
- 입력: `db`(요청의 DB 세션. `create_prescription()`과 같은 트랜잭션에서 가이드 행을 만들기 위함), `prescription_id`, `background_tasks`(FastAPI `BackgroundTasks`). `db`와 `background_tasks`는 요청 핸들러에서 `create_prescription()`을 거쳐 넘겨받습니다
- 출력: 만든 `guide_id` 2개(`medication`, `lifestyle`). 진행 상태는 7-1로 확인합니다.
- 처리 순서:
  1. `create_prescription()`과 같은 트랜잭션 안에서 `guides`에 두 행을 `status = generating`으로 만들고, 가이드마다 `run_guide_generation(guide_id)`를 `background_tasks`에 등록합니다. 등록된 작업은 응답을 보낸 뒤(트랜잭션 커밋 뒤) 실행됩니다.
  2. 확정 처방(`get_confirmed_prescription()`, 설아), 건강 프로필, 복용 시각(`dose_schedules`)을 읽습니다.
  3. 근거 검색: 약마다 약품명으로 좁혀 검색하고 상위 5개를 씁니다(GUIDE-003).
  4. 숫자 칸과 `easy_text`는 확정 처방 값으로 코드 틀을 채우고, LLM은 설명 칸만 씁니다.
  5. `status = verifying`으로 바꾸고 `verify_guide()`(채민)로 검증합니다.
  6. 통과 → `completed` / 틀린 항목이 있으면 7-1 비고의 표대로 문장을 바꾸고 `check: "fallback"`(생활습관은 항목 빼기) → `completed_with_replacements` / LLM 오류·30초 초과 → `failed`(`content = NULL`)
  - 검증 호출: 복약 가이드는 `verify_guide(guide, prescription, guide_id=…, kind="medication")`, 생활습관 가이드는 같은 함수에 `kind="lifestyle"`, `user_conditions`를 넘깁니다. 1차는 다시 쓰기가 없어 가이드마다 한 번만 부르고, 시도 횟수 인자(`attempt_no`·`is_last_attempt`)는 넘기지 않습니다(6장과 같음).
  - 약 단위 실패(숫자 불일치·빠진 약)는 코드 틀 때문에 생기지 않아야 합니다. 만약 생기면 코드 오류로 보고 기록을 남긴 뒤 그 가이드를 `failed`로 처리합니다.
- 비고:
  - 1차 실행 방식: `start_guide_generation(db, prescription_id, background_tasks)`로 인자를 받아 FastAPI `BackgroundTasks`로 돌립니다(민정님 질문 ①안). `asyncio.create_task()`(②안)는 트랜잭션 커밋 전에 작업이 시작돼 가이드 행을 못 읽을 수 있어서 쓰지 않습니다. 그래서 `create_prescription()`도 `background_tasks`를 받아 자기 `db` 세션과 함께 넘겨 주세요(OCR 확정·직접 입력 두 API 모두). 가이드 행은 넘겨받은 `db`로 만듭니다. `start_guide_generation()`은 커밋하지 않고, 커밋은 `create_prescription()`을 부른 API(`POST /prescriptions`, `POST /scans/{scan_id}/confirm`)가 합니다(4장과 같음). 2차에 `ai_worker`로 옮길 때 같은 `run_guide_generation(guide_id)`를 그대로 부릅니다(백엔드 전달사항 2-3).
  - `run_guide_generation()`은 백그라운드에서 **DB 세션을 새로 열어서** 씁니다. 요청 핸들러의 세션은 응답 후 닫히기 때문입니다.
  - 1회 용량의 `min`·`max`·`parsed`는 ERD에 칸이 없어 `get_confirmed_prescription()`(설아)이 `dose_text`를 표현 사전(채민)으로 읽어 만듭니다. 직접 입력은 `min = max`입니다(✅ 5장 `get_confirmed_prescription()` 반영)
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
| 2026-11-23 | 설아 | 5장 작성: `GET /home?date=`(`/home/today`에서 변경), `GET /prescriptions`, `GET /prescriptions/{prescription_id}`, `GET /prescription-items/{prescription_item_id}`(`/drugs/{drug_id}`에서 변경) + 내부 함수 `get_confirmed_prescription()`. `prescription_drug_id` → `prescription_item_id`. 3번 목록: 설아 담당 → 리뷰 요청, `/users/me`·건강 프로필 API 2개 구현 담당을 설아로 변경(명세는 4장) |
| 2026-11-23 | 설아 | 5장 관련 다른 섹션 반영: 4장 `/home/today` → `/home?date=`, 4-9 23·24 ✅, `validate_drug_input()`·`format_condition_label()` 공용 함수 / 6장 약 상세 경로, `PATCH /dose-conditions`·6-1·확정 API 이동 화면(홈), `DELETE /scans/{scan_id}` 추가, 페이지 순서·문서 종류 경고 답변 / 7장 7-1 `how_to_take` 조회 때 채우기, 설아 확인 항목 ✅ |
| 2026-11-23 | 설아 | 요구사항 정의서 교차 검증 반영: 7-1 실패 문구를 '가이드 생성이 지연되고 있어요'로 통일, 4장 `POST /prescriptions` 병원명·메모는 1차 화면에서 보내지 않음, 6장 같은 파일 감지·다른 처방전 섞임 안내 2차 |
| 2026-11-23 | 설아 | `PATCH /prescription-items` 1차 제외(채민님 의견): '복용 조건 확인 필요' 약은 약 상세(C-2)에서도 6장 `PATCH /dose-conditions`로 회차마다 고름. 3번 목록 28개, 4-9 23·24, 5장 약 상세 비고·에러 코드, 6장 관련 화면, 7-1 비고 수정 |
| 2026-11-23 | 설아 | 서버 도메인 `api.daol.site` 반영(daol.site 구매): 3-1 배포 두 행(Elastic IP·Let's Encrypt·rewrites 주소), 4-1 쿠키 행(Vercel → EC2 구간도 HTTPS)·Plan B 문구 |
| 2026-11-23 | 설아 | 채민님 리뷰 반영: `expired`·`DOCUMENT_EXPIRED` 문구를 '파일이 삭제됐어요. 다시 올려 주세요'로 통일(취소에도 맞게), `DELETE /scans` 비고에 정리 작업이 파일이 남은 `confirmed`·`expired` 문서도 지운다고 추가 |
| 2026-11-23 | 설아 | 유정님 리뷰 반영: 7-4 '복용 중인 약' 기준을 5-0(종료일이 오늘 이후)으로 통일, 5장 약 상세 `source_name`은 약마다 달라질 수 있다는 메모 추가 |
| 2026-11-23 | 설아 | 5장 약 상세 `source_name`을 `drugs.data_source`(`easy_drug` / `permit`)로 정하도록 수정, 기준일은 `data_fetched_at`(ERD `drugs`에 `data_source`·`source_updated_at`·`is_otc` 추가, 11/23 유정·민정) |
| 2026-11-23 | 설아 | 민정님 리뷰 반영: 4장에 `get_daily_intakes()` 이름·위치·커밋 규칙과 `schedule_check_items` 규칙 추가, `validate_drug_input(drug, *, index, manual)`를 `create_prescription()`이 직접 부르도록 정리, 문구 함수를 `format_condition_label()`(회차)·`format_condition_summary()`(약)로 나누고 `/intakes`·`/home`의 `as_needed_items`·`schedule_check_items` 칸을 `condition_summary`로 변경, 4-9 23·24와 `reason` 섞임 이유 문장 수정 |
| 2026-11-23 | 유정 | 7-7 검증 호출에서 `attempt_no`·`is_last_attempt` 제거(6장과 맞춤), 7-3 처방일 없을 때 등록일 표시 반영, pgvector 사용 반영 |
| 2026-11-20 | 유정 | 7-1 건강 프로필을 나중에 입력한 경우의 상단 문구 추가(4장 건강 프로필 비고 답변) |
| 2026-11-20 | 유정 | 7-7 커밋 위치 표현을 4장과 맞춤(커밋은 `create_prescription()`을 부른 API) |
| 2026-11-20 | 유정 | 7-7 시그니처를 `start_guide_generation(db, prescription_id, background_tasks)`로 변경(같은 트랜잭션에서 가이드 행 생성), 챗봇 검사 결과 저장 칸 `chat_messages.check_result` 반영 |
| 2026-11-20 | 유정 | 7장 민정님 리뷰 반영: 30초 초과는 조회 때도 `failed` 처리·다시 시도 때 `updated_at` 갱신, 가이드 행 없을 때 처리, `start_guide_generation(prescription_id, background_tasks)`·새 DB 세션, 응답 키 항상 포함, `used_default_profile` 기준, 챗봇 `streaming` 60초 규칙, fetch 스트림 안내 |
| 2026-11-20 | 유정 | 7장 검증 흐름 반영(채민님 코멘트): `easy_text` 코드 틀, `fallback` 문장 바꾸기 규칙, 생활습관 `kind="lifestyle"`·항목 빼기, 챗봇 `check_full()` 기록만 |
| 2026-11-20 | 유정 | 7장 리뷰 반영: `failed`·30초 기준 확정 표시, 가이드 `dose_times`는 조회 때 시간표 값으로 채움(채민님 제안), 생활습관 가이드 검증 확인 요청 추가 |
| 2026-11-20 | 민정 | 4번 섹션 작성: API 10개 + 내부 함수 `create_prescription()`·`recalculate_schedule()`, 영역 에러 코드, 리프레시 토큰 쿠키 규칙, 1차 ERD 대조(4-8 E1~E11). 3번 목록 민정 담당 → 리뷰 요청 |
| 2026-11-20 | 민정 | 6·7장 반영: 처방 입력을 6장 확정 API 모양으로 통일(ERD 매핑표), `background_tasks`·가이드 행 같은 트랜잭션, 복용 기록 생성 시점·재계산 함수, 6장 질문 답(4-9 19~22) |
| 2026-11-20 | 민정 | 공통 규칙 변경: 1-1 `fields` 형식, 1-3 SSE 표를 7-6 기준으로 수정, 1번 형식·목록 규칙에 예외(처방 입력 모양, `GET /drugs`) 추가 |
| 2026-11-20 | 민정 | 3-1에 개인정보 가리기 함수 `mask_text()`(채민) 추가(7장 요청) |
| 2026-11-23 | 민정 | 설아님 리뷰 반영(쿠키): 4-1 리프레시 토큰 쿠키 `SameSite=None` → `Lax`, Vercel rewrites로 퍼스트파티 쿠키·CORS credentials 제거, Plan B(`daol.site` / `api.daol.site`) 추가. 로그아웃 쿠키 삭제 헤더, 3-1 배포 두 행, 7-6 SSE 비고(프록시 테스트) 함께 수정 |
| 2026-11-23 | 민정 | 설아님 리뷰 반영(홈·처방): `GET /intakes` `schedule_check_items`에 회차별 `conditions` 추가(4-9 23), `POST /prescriptions` 저장 후 이동을 '홈'으로, 건강 프로필 팝업·필요시 토글·이름 그대로 저장 버튼·처방일 없을 때 등록일 표시 반영, 만 14세 미만 `VALIDATION_ERROR` 규칙 추가, 필요시 약 체크 1차 제외 확정, 4-8 E4(`talk_message` 1차 제외) 확정, 4-9 1·4·5·6·10·12·18 확정 |
| 2026-11-23 | 민정 | 리뷰 반영(설아·채민·유정): `GET /intakes` `schedule_check_items`에 약 단위 `reason`·`prescription_id` 추가, `timing_unknown`은 `conditions` 없이 안내 카드용으로 내려줌(4-9 23), 4-9 24(`PATCH /prescription-items`) 추가, 4-8 E2(2차)·E9(`rule / user`)·E10(`times_per_day` NULL 허용)·E11(`check_result` jsonb, 저장 형식) 확정, `create_prescription()` `parsed_by` 값·공통 검사(`is_oral`, 입력 범위) ERD v2에 맞춤 |
| 2026-11-20 | 유정 | 7장 가이드·챗봇 작성: API 6개 + 내부 함수 1개. 1차 축소안 반영(자동 재시도·다시 만들기·피드백·이전 대화는 2차), SSE 이벤트는 백엔드 합의 이름(`delta`·`text`·`physical/self_harm`)으로 작성 |
| 2026-11-21 | 채민 | 6장 4장 리뷰(PR #15) 반영: 4-9 답변 항목 ✅ 표시, 확정 처리 순서를 `create_prescription()`·커밋 위치에 맞춤, `GET /drugs`·매칭 후보 칸 이름을 ERD(`item_name`·`company`)로 변경, `recalculate_schedule()` 연결, `parsed_by` ERD 값 확인 요청 추가 |
| 2026-11-22 | 채민 | 6장 ERD v2(`daol_erd_v2.dbml`) 대조 반영: 1차 LLM 복용법 해석 제외(`parsed_by` = `rule` / `user`), `pill_envelope`, 확정 Body `drug_name`(처방전 이름)·`raw_text`, `is_oral`, 입력 범위, `parse_document_v1`, 챗봇 기록 칸 제안 |
| 2026-11-25 | 채민 | 6장 PR #25 리뷰 반영: 확정 응답 예시 `reason`을 `timing_unknown`으로 수정(민정님), 6-2·`PATCH /scans` 비고에 '고친 용량을 읽을 수 없으면 `needs_check: true`' 예외와 `dose_per_time.edited` 추가(설아님) |
| 2026-11-26 | 유정 | 출처 칸 맞춤(ERD #41, 약 정보는 drugs 직접 조회): 7-1·7-6 예시의 약 출처 `rag_document_id` → `drug_id`, 7-1 비고에 출처 규칙 추가, 1-3 SSE 표 `sources` 예시와 6장 근거 대조 문장도 같게 맞춤(설아님 리뷰) |
| 2026-11-26 | 채민 | 6-2 확인 표시 규칙 추가: 정·캡슐·포 1회 용량 0.25 미만이면 `needs_check: true`(OCR·고친 용량), `is_oral: false` 줄은 `dosage.needs_confirm: false` |
| 2026-11-26 | 민정 | 1-1 `VALIDATION_ERROR` 응답 예시·필드 경로(대괄호)·대표 문구 추가, 4-1 `/auth/refresh` 비고에 재발급 때 만료일 14일 갱신 추가(#46 리뷰, #50) |
