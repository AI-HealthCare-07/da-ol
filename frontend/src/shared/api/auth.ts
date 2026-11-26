import { api } from "./client";
import type { KakaoLoginResponse, Me } from "./types";

export const kakaoLogin = (code: string) =>
  api<KakaoLoginResponse>("/auth/kakao", { method: "POST", body: { code }, auth: false });

export const logout = () => api<void>("/auth/logout", { method: "POST" });

export const getMe = () => api<Me>("/users/me");

export type ConsentType = "terms" | "privacy" | "sensitive_health";
export interface ProfileInput {
  name: string;
  birth_date: string; // YYYY-MM-DD
  gender: "male" | "female";
  consents: { consent_type: ConsentType; agreed: boolean }[];
}

// A-1-2 추가 정보 + 필수 약관 동의 (명세 4장). 응답은 GET /users/me와 같은 모양
export const saveProfile = (body: ProfileInput) => api<Me>("/users/me/profile", { method: "POST", body });
