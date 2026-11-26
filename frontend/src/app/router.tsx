import { createBrowserRouter } from "react-router";
import { GuestOnly, RequireAuth, RequireIncompleteProfile } from "@/app/guards";
import AppLayout from "@/app/layouts/AppLayout";
import { HomePage } from "@/pages/home";
import { KakaoCallbackPage, LoginPage } from "@/pages/login";
import { ProfileSetupPage } from "@/pages/profile-setup";
import Placeholder from "@/shared/ui/Placeholder";

// 화면 번호는 와이어프레임(docs/planning/daol_wireframe.md) 기준
export const router = createBrowserRouter([
  {
    element: <GuestOnly />,
    children: [{ path: "/login", element: <LoginPage /> }], // A-1-1
  },
  { path: "/auth/kakao/callback", element: <KakaoCallbackPage /> },
  {
    element: <RequireIncompleteProfile />,
    children: [{ path: "/signup/profile", element: <ProfileSetupPage /> }], // A-1-2
  },
  {
    element: <RequireAuth />,
    children: [
      {
        element: <AppLayout />, // 헤더 + 하단 탭 + 챗봇 버튼
        children: [
          { path: "/", element: <HomePage />, handle: { tab: "home" } }, // A-2
          { path: "/meds", element: <Placeholder code="C-1" title="내 약" />, handle: { tab: "meds" } },
          { path: "/guides", element: <Placeholder code="D-1" title="가이드" />, handle: { tab: "guides" } },
          { path: "/my", element: <Placeholder code="E-1" title="마이페이지" />, handle: { tab: "my" } },
        ],
      },
      {
        element: <AppLayout sub />, // 하위 화면: 뒤로가기 + 제목, 탭 없음
        children: [
          { path: "/register", element: <Placeholder code="B-1" title="처방 등록" />, handle: { title: "처방 등록", hideChat: true } },
          { path: "/register/manual", element: <Placeholder code="B-1-3" title="직접 입력" />, handle: { title: "직접 입력" } },
          { path: "/scans/:scanId", element: <Placeholder code="B-2" title="인식 결과 확인" />, handle: { title: "인식 결과 확인" } },
          { path: "/meds/prescriptions/:prescriptionId", element: <Placeholder code="C-1" title="처방 상세" />, handle: { title: "처방 상세" } },
          { path: "/meds/items/:itemId", element: <Placeholder code="C-2" title="약 상세" />, handle: { title: "약 상세" } },
          { path: "/guides/:prescriptionId", element: <Placeholder code="D-2" title="가이드" />, handle: { title: "가이드" } },
          { path: "/my/health", element: <Placeholder code="E-2" title="건강 프로필" />, handle: { title: "건강 프로필" } },
          { path: "/chat", element: <Placeholder code="F-1" title="AI 복약 상담" />, handle: { title: "AI 복약 상담", hideChat: true } },
        ],
      },
    ],
  },
  { path: "*", element: <Placeholder code="404" title="페이지를 찾을 수 없어요" /> },
]);
