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

## 폴더

```text
src/
├── api/          # API 호출 (client.ts 하나를 모두 거침), 응답 타입, 가짜 데이터
├── auth/         # 로그인 상태, 화면 접근 규칙
├── app/          # 화면 주소 (화면 번호는 와이어프레임 기준)
├── components/
│   ├── layout/   # 헤더, 하단 탭, 챗봇 버튼
│   └── home/     # 홈 회전 약통 3D
├── lib/          # 카카오 로그인 등
└── pages/        # 화면
```

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
