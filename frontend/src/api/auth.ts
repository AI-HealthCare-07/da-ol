import { api } from "./client";
import type { KakaoLoginResponse, Me } from "./types";

export const kakaoLogin = (code: string) =>
  api<KakaoLoginResponse>("/auth/kakao", { method: "POST", body: { code }, auth: false });

export const logout = () => api<void>("/auth/logout", { method: "POST" });

export const getMe = () => api<Me>("/users/me");
