import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { refreshAccessToken, setAccessToken, setAuthHandlers } from "../api/client";
import { getMe, logout as logoutApi } from "../api/auth";
import type { Me } from "../api/types";
import { USE_MOCK } from "../api/home";

type Status = "loading" | "guest" | "signed-in";

interface AuthValue {
  status: Status;
  me: Me | null;
  signIn: (accessToken: string) => Promise<Me>; // 카카오 로그인 성공 직후
  reloadMe: () => Promise<Me | null>;
  applyMe: (me: Me) => void; // 추가 정보 저장 응답처럼 이미 받은 내 정보로 갱신
  signOut: () => Promise<void>;
}

const AuthContext = createContext<AuthValue | null>(null);

const MOCK_ME: Me = {
  user_id: 0, nickname: "다올이", email: null, name: "김다올", birth_date: "1958-03-14",
  gender: "female", is_profile_completed: true, created_at: "2026-11-20T10:12:00+09:00",
};
// VITE_MOCK_NEW_USER=true면 처음 가입한 회원처럼 추가 정보 입력(A-1-2)부터 보여 줍니다
const MOCK_START: Me =
  import.meta.env.VITE_MOCK_NEW_USER === "true"
    ? { ...MOCK_ME, name: null, birth_date: null, gender: null, is_profile_completed: false }
    : MOCK_ME;

export function AuthProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<Status>(USE_MOCK ? "signed-in" : "loading");
  const [me, setMe] = useState<Me | null>(USE_MOCK ? MOCK_START : null);

  const goGuest = useCallback(() => {
    setAccessToken(null);
    setMe(null);
    setStatus("guest");
  }, []);

  const reloadMe = useCallback(async () => {
    try {
      const m = await getMe();
      setMe(m);
      setStatus("signed-in");
      return m;
    } catch {
      goGuest();
      return null;
    }
  }, [goGuest]);

  // 앱 시작: 메모리에 토큰이 없으니 쿠키로 재발급 → 내 정보로 라우팅 결정
  useEffect(() => {
    if (USE_MOCK) return;
    setAuthHandlers({
      onSessionExpired: goGuest,
      onProfileRequired: () => setMe((m) => (m ? { ...m, is_profile_completed: false } : m)),
    });
    refreshAccessToken()
      .then(() => reloadMe())
      .catch(goGuest);
  }, [goGuest, reloadMe]);

  const signIn = useCallback(async (token: string) => {
    setAccessToken(token);
    const m = await getMe();
    setMe(m);
    setStatus("signed-in");
    return m;
  }, []);

  const signOut = useCallback(async () => {
    if (!USE_MOCK) {
      try {
        await logoutApi();
      } catch {
        /* 이미 로그아웃된 경우도 성공으로 봅니다 (명세 4장) */
      }
    }
    goGuest();
  }, [goGuest]);

  const applyMe = useCallback((m: Me) => {
    setMe(m);
    setStatus("signed-in");
  }, []);

  const value = useMemo(
    () => ({ status, me, signIn, reloadMe, applyMe, signOut }),
    [status, me, signIn, reloadMe, applyMe, signOut],
  );
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("AuthProvider 안에서만 쓸 수 있어요");
  return ctx;
}
