<div align="center">

<!-- 로고 이미지가 준비되면 아래 경로에 넣어주세요 -->
<img src="docs/assets/logo.png" width="600" alt="다올 로고" />

# 다올 (Da-Ol)

**진료 기록 기반 복약 안내 및 생활 습관 개선 가이드 자동 생성 시스템**

*다(전부) + 올(올바른) — 올바른 복약 안내와 생활 습관 개선을 모두 아우르는 서비스*

</div>

---

## 📌 프로젝트 소개

진료 기록을 바탕으로 환자에게 꼭 필요한 **복약 안내**와 **생활 습관 개선 가이드**를 자동으로 만들어 주는 AI 웹 서비스입니다.

- **개발 기간**: 2026.11.16 ~ 2026.12.30
- **과정**: 오즈코딩스쿨 AI 헬스케어 부트캠프 Final Project

### 이런 문제를 해결하고 싶어요

> 하루에 챙겨야 할 약이 너무 많아요, 이 약들을 같이 복용해도 되는지, 언제 복용하는 게 가장 효과적인지 모르겠어요

### 주요 기능

| 기능 | 설명 |
| --- | --- |
| 진료 기록 입력 | (작성 예정) |
| 복약 안내 생성 | (작성 예정) |
| 생활 습관 개선 가이드 생성 | (작성 예정) |
| (추가 기능) | (작성 예정) |

---

## 🛠 기술 스택

| 구분 | 기술 |
| --- | --- |
| Frontend | (작성 예정) |
| Backend | FastAPI, Tortoise ORM, Pydantic |
| AI / LLM | (작성 예정) |
| Database | PostgreSQL (pgvector), Redis |
| Infra / 배포 | Docker Compose, Nginx, AWS EC2 |
| 패키지 관리 | uv |
| 코드 품질 | Ruff, Mypy, Pytest |
| 협업 도구 | GitHub, Discord, Notion |

---

## 🏗 시스템 구조

API 서버(FastAPI)와 AI 작업을 처리하는 워커(AI Worker)를 분리한 구조입니다. 복약 안내·생활 습관 가이드 생성처럼 시간이 걸리는 AI 작업은 워커가 맡고, API 서버는 요청 처리에 집중합니다.

> (작성 예정) 아키텍처 다이어그램, ERD

### 📂 디렉터리 구조

```text
.
├── ai_worker/          # AI 모델 추론 및 학습 관련 코드 (Worker)
│   ├── core/           # 워커 설정 및 로거
│   ├── models/         # AI 모델 파일 보관
│   ├── tasks/          # 실제 처리할 작업 정의
│   └── main.py         # 워커 진입점
├── app/                # FastAPI 서버 코드
│   ├── apis/           # API 라우터 (v1 버전 관리)
│   ├── core/           # 서버 설정 (pydantic-settings), DB 설정, JWT, Validator 등 핵심 기능
│   ├── dtos/           # 데이터 전송 객체 (Pydantic models)
│   ├── models/         # DB 테이블 정의
│   ├── services/       # 비즈니스 로직
│   └── main.py         # FastAPI 애플리케이션 진입점
├── docs/               # 회의록, 팀 규칙 등 문서
├── envs/               # 환경 변수 설정 파일 (.env)
├── infra/              # 인프라 설정 관련 디렉터리
│   ├── docker/         # Docker Compose 설정 (운영용)
│   └── nginx/          # Nginx 설정 파일 (리버스 프록시)
├── scripts/            # 배포 및 CI용 쉘 스크립트
├── docker-compose.yml  # 로컬 개발용 서비스 실행 설정
└── pyproject.toml      # uv 기반 의존성 관리 설정
```

---

## 🚀 실행 방법

### 1. 사전 준비

- **Python** 3.13 이상
- **uv** ([설치 가이드](https://github.com/astral-sh/uv))
- **Docker & Docker Compose**

### 2. 레포지토리 clone

```bash
git clone https://github.com/AI-HealthCare-07/da-ol.git ~/PycharmProjects/da-ol
cd ~/PycharmProjects/da-ol
```

### 3. 의존성 설치

```bash
# 전체 의존성 설치 (가상환경 .venv 자동 생성)
uv sync

# 특정 그룹만 설치하려는 경우
uv sync --group app  # API 서버용
uv sync --group ai   # AI 워커용
```

설치 후 PyCharm에서 `Settings → Project → Python Interpreter`로 들어가 `.venv`를 인터프리터로 선택해주세요.

### 4. 환경 변수 설정

`envs/`의 예시 파일을 복사해서 `.env` 파일을 만든 뒤, 내용을 상황에 맞게 수정합니다.

```bash
cp envs/example.local.env envs/.local.env   # 로컬용
cp envs/example.prod.env envs/.prod.env     # 배포용
```

> ⚠️ `.env` 파일에는 비밀번호·API 키가 들어가므로 절대 커밋하지 마세요.

### 5. 서버 실행

**Docker Compose로 전체 실행** (API, Worker, DB, Redis, Nginx)

```bash
docker compose up -d --build
```

실행 후 [http://localhost/api/docs](http://localhost/api/docs)에서 Swagger UI를 확인할 수 있습니다.

**개별 실행** (개발용)

```bash
# FastAPI 서버
uv run uvicorn app.main:app --reload

# AI Worker
uv run python -m ai_worker.main
```

---

## 🧪 테스트 및 코드 품질

PR을 올리기 전에 아래 스크립트로 확인해주세요.

```bash
./scripts/ci/run_test.sh          # 테스트 (Pytest)
./scripts/ci/code_fommatting.sh   # 코드 포맷팅 (Ruff)
./scripts/ci/check_mypy.sh        # 정적 타입 검사 (Mypy)
```

---

## 📝 개발 가이드

- **API 추가**: `app/apis/v1/` 아래에 라우터 파일을 만들고 `app/apis/v1/__init__.py`에 등록합니다.
- **DB 모델 추가**: `app/models/`에 Tortoise 모델을 정의하고 `app/db/databases.py`의 `MODELS` 리스트에 추가합니다.
- **AI 로직 추가**: `ai_worker/tasks/`에 처리 로직을 작성하고 `ai_worker/main.py`에서 호출하도록 구성합니다.

---

## 🤝 협업 규칙

> 자세한 내용은 [팀 규칙](docs/team_rules.md)을 확인해주세요.

### 소통 채널

- **Discord**: 실시간 소통, PR·리뷰 요청 알림 (GitHub 웹훅 연동)
- **Notion**: 회의록, 요구사항 정의서 등 산출물 정리
- **GitHub**: 코드 관리, 이슈·PR

### 브랜치 전략 (초안)

```
main        배포용 (직접 push 금지)
└─ dev      개발 통합 브랜치
   └─ feat/기능명    기능 개발
   └─ fix/버그명     버그 수정
```

### 커밋 메시지 규칙 (초안)

| 태그 | 의미 |
| --- | --- |
| `feat` | 새로운 기능 추가 |
| `fix` | 버그 수정 |
| `docs` | 문서 수정 |
| `refactor` | 코드 리팩토링 |
| `style` | 코드 포맷팅 (동작 변화 없음) |
| `test` | 테스트 코드 |
| `chore` | 빌드, 설정 파일 등 기타 |

예시: `feat: 복약 안내 생성 API 추가`

### PR 규칙 (초안)

1. 작업 브랜치에서 `dev`로 PR을 올립니다.
2. 최소 1명 이상의 리뷰 승인 후 머지합니다.
3. PR이 올라오면 Discord로 알림이 가고, 재리뷰 요청 시 리뷰어가 멘션됩니다.

---

## 📚 문서

- [회의록](docs/meetings/)
- [팀 규칙](docs/team_rules.md)
- 요구사항 정의서 (작성 예정)
- API 명세서 (작성 예정)
