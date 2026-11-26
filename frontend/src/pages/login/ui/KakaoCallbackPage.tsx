import { useEffect, useRef } from "react";
import { useNavigate, useSearchParams } from "react-router";
import { kakaoLogin } from "@/shared/api/auth";
import { ApiError } from "@/shared/api/client";
import { useAuth } from "@/app/providers/AuthProvider";
import { checkKakaoState } from "@/shared/lib/kakao";

// 카카오가 돌려보낸 code로 로그인합니다.
// 인가 코드는 한 번만 쓸 수 있어서, 개발 모드(StrictMode)에서 두 번 불리지 않게 막습니다.
const usedCodes = new Set<string>();

export default function KakaoCallbackPage() {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const { signIn } = useAuth();
  const started = useRef(false);

  useEffect(() => {
    if (started.current) return;
    started.current = true;

    const fail = (error: string) => {
      void navigate("/login", { replace: true, state: { error } });
    };
    if (params.get("error") === "access_denied") return fail("카카오 로그인이 취소되었어요");
    const code = params.get("code");
    if (!code) return fail("카카오 로그인에 실패했어요. 다시 시도해 주세요");
    // 이미 처리 중인 code면 그냥 끝냅니다. state 확인보다 먼저 해야 합니다:
    // state는 한 번 꺼내면 지워지므로, 두 번째 호출이 state 확인을 먼저 하면 실패로 빠집니다.
    if (usedCodes.has(code)) return;
    usedCodes.add(code);
    if (!checkKakaoState(params.get("state"))) return fail("카카오 로그인에 실패했어요. 다시 시도해 주세요");

    kakaoLogin(code)
      .then(async (res) => {
        await signIn(res.access_token);
        void navigate(res.is_profile_completed ? "/" : "/signup/profile", { replace: true });
      })
      .catch((e: unknown) => fail(e instanceof ApiError ? e.message : "카카오 로그인에 실패했어요. 다시 시도해 주세요"));
  }, [navigate, params, signIn]);

  return <div className="flex min-h-screen items-center justify-center text-ink-sub">로그인하는 중…</div>;
}
