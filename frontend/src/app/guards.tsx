import { Navigate, Outlet, useLocation } from "react-router";
import { useAuth } from "@/app/providers/AuthProvider";

function Splash() {
  return <div className="flex min-h-screen items-center justify-center text-ink-sub">불러오는 중…</div>;
}

// 로그인한 회원만. 추가 정보 입력 전이면 A-1-2로 보냅니다 (PROFILE_REQUIRED).
export function RequireAuth() {
  const { status, me } = useAuth();
  const loc = useLocation();
  if (status === "loading") return <Splash />;
  if (status === "guest") return <Navigate to="/login" replace state={{ from: loc.pathname }} />;
  if (me && !me.is_profile_completed) return <Navigate to="/signup/profile" replace />;
  return <Outlet />;
}

// 추가 정보 입력 화면: 로그인은 했지만 아직 입력 전인 회원만
export function RequireIncompleteProfile() {
  const { status, me } = useAuth();
  if (status === "loading") return <Splash />;
  if (status === "guest") return <Navigate to="/login" replace />;
  if (me?.is_profile_completed) return <Navigate to="/" replace />;
  return <Outlet />;
}

// 로그인 화면: 이미 로그인했으면 홈으로
export function GuestOnly() {
  const { status } = useAuth();
  if (status === "loading") return <Splash />;
  if (status === "signed-in") return <Navigate to="/" replace />;
  return <Outlet />;
}
