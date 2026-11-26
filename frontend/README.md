# 다올 프론트엔드

React 19 + Vite + TypeScript + Tailwind CSS v4 + React Router. 홈 약통은 three.js(3D)입니다.

## 처음 실행

```bash
cd frontend
npm install
cp .env.example .env.local   # 값 채우기 (커밋 금지)
npm run dev                  # http://localhost:5173
```

- `VITE_USE_MOCK=true`: 백엔드 없이 가짜 데이터로 홈 화면을 띄웁니다. 로그인도 건너뜁니다.
- `VITE_USE_MOCK=false`: `/api` 요청을 `VITE_DEV_API_TARGET`(기본 `http://localhost:8000`)로 넘깁니다.
- 지원 브라우저는 크롬입니다 (REQ-NFR-008).

## 폴더 (FSD, Pages First)

[Feature-Sliced Design](https://feature-sliced.design/) v2.1의 Pages First 방식을 따릅니다. 처음부터 잘게 나누지 않고, 화면(`pages`) 안에 두었다가 여러 화면에서 쓰게 되면 그때 아래 층으로 꺼냅니다.

```text
src/
├── main.tsx
├── app/                  # 앱 전체에 걸리는 것
│   ├── router.tsx        # 화면 주소 (화면 번호는 와이어프레임 기준)
│   ├── guards.tsx        # 화면 접근 규칙 (로그인·추가 정보 입력 여부)
│   ├── providers/        # 로그인 상태(AuthProvider)
│   ├── layouts/          # 헤더, 하단 탭, 챗봇 버튼
│   └── styles/           # 전역 CSS
├── pages/                # 화면 하나 = 슬라이스 하나
│   ├── home/             # A-2 홈 (회전 약통 3D 포함)
│   │   ├── ui/
│   │   ├── api/
│   │   └── index.ts      # 슬라이스 입구: 밖에서 쓸 것만 내보냄
│   ├── login/            # A-1-1 로그인, 카카오 콜백
│   └── profile-setup/    # A-1-2 추가 정보 입력
└── shared/               # 특정 화면에 묶이지 않는 공용 코드
    ├── api/              # API 클라이언트(client.ts 하나를 모두 거침), 공통 응답 타입, 가짜 데이터
    ├── config/           # 환경 변수 설정 (USE_MOCK 등)
    ├── lib/              # 날짜(KST), 카카오 로그인 등
    └── ui/               # 공용 UI (Placeholder 등)
```

### 폴더 규칙

1. **한 화면에서만 쓰는 코드는 `pages/화면이름/` 안에 둡니다.** 화면 컴포넌트는 `ui/`, 그 화면 전용 API 호출은 `api/`에 둡니다.
2. **두 화면 이상에서 쓰게 되면 그때 아래 층으로 꺼냅니다.** 미리 빈 폴더를 만들지 않습니다.
   - `widgets/`: 여러 화면에 들어가는 큰 UI 덩어리 (예: 처방 요약 블록)
   - `features/`: 회원이 하는 행동 (예: 약 추가하기)
   - `entities/`: 업무 대상 (예: 약 카드, 처방)
3. **위 층은 아래 층만 가져옵니다.** `app` → `pages` → `widgets` → `features` → `entities` → `shared` 순서이고, 같은 층의 다른 슬라이스끼리는 가져오지 않습니다(예: `pages/home`이 `pages/login`을 가져오면 안 됨).
4. **다른 층에서 가져올 때는 `@/`로 시작하는 경로를 씁니다.** 예: `import { api } from "@/shared/api/client";` 같은 슬라이스 안에서는 상대 경로(`./`, `../`)를 씁니다.
5. **다른 슬라이스는 입구(`index.ts`)로만 가져옵니다.** 예: `import { HomePage } from "@/pages/home";`
6. **슬라이스 이름은 백엔드 기능 이름과 맞춥니다.** 예: `scan`(처방 사진 인식), `prescription`, `guide`, `chat`

## 정해 둔 규칙

1. API는 항상 상대 경로 `/api/v1/...`로 부릅니다. 로컬은 개발 서버 프록시, 배포는 `vercel.json` rewrites가 `https://api.daol.site`로 넘깁니다. 그래서 리프레시 토큰 쿠키가 같은 사이트 쿠키로 따라갑니다(명세 4-1).
2. 액세스 토큰은 메모리에만 둡니다. 새로고침하면 쿠키로 재발급받습니다.
3. 401이 여러 개 동시에 와도 재발급은 한 번만 부릅니다(single-flight).
4. 복용 체크는 약 하나씩 `PATCH /intakes/{intake_id}`. [먹었어요]처럼 칸 전체를 체크할 때는 동시에 보내지 않고 하나씩 순서대로 보냅니다(꽃 판단이 어긋나지 않게).
5. 본문 글자 16px 이상, 누를 수 있는 것은 최소 44×44 (`tap` 클래스).

## 배포 (Vercel)

- Root Directory: `frontend`
- Build Command: `npm run build`, Output: `dist`
- 환경 변수: `VITE_KAKAO_CLIENT_ID`, `VITE_KAKAO_REDIRECT_URI`(`https://daol.site/auth/kakao/callback`), `VITE_USE_MOCK=false`
