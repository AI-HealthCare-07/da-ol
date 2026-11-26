import { useLocation } from "react-router";
import { goKakaoLogin } from "@/shared/lib/kakao";

// A-1-1 로그인. 카카오만 제공합니다.
export default function LoginPage() {
  const loc = useLocation();
  const error = (loc.state as { error?: string } | null)?.error;
  return (
    <div className="mx-auto flex min-h-screen max-w-[480px] flex-col justify-between px-6 py-16">
      <div className="mt-16 text-center">
        <h1 className="text-3xl font-bold text-leaf">다올</h1>
        <p className="mt-3 text-ink-sub">처방전 한 장으로 복약 안내와 생활 습관 가이드를</p>
      </div>
      <div>
        {error && <p className="mb-4 rounded-xl bg-white p-3 text-center text-[15px] text-ink">{error}</p>}
        <button
          className="tap w-full rounded-2xl bg-[#FEE500] py-4 text-lg font-bold text-[#191919]"
          onClick={goKakaoLogin}
        >
          카카오로 시작하기
        </button>
      </div>
    </div>
  );
}
