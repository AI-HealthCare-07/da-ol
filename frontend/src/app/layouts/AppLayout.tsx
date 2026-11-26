import { Link, NavLink, Outlet, useMatches, useNavigate } from "react-router";
import { useAuth } from "@/app/providers/AuthProvider";

interface RouteHandle {
  tab?: "home" | "meds" | "guides" | "my";
  title?: string;
  hideChat?: boolean;
}

const TABS = [
  { to: "/", label: "홈", end: true },
  { to: "/meds", label: "내 약" },
  { to: "/register", label: "+ 처방 등록", center: true },
  { to: "/guides", label: "가이드" },
  { to: "/my", label: "마이페이지" },
];

// 360px 모바일 기준, 넓은 화면에서는 가운데에 폭을 제한합니다 (홈 PC 배치는 나중에 따로).
export default function AppLayout({ sub = false }: { sub?: boolean }) {
  const matches = useMatches();
  const handle = (matches[matches.length - 1]?.handle ?? {}) as RouteHandle;
  const navigate = useNavigate();
  const { signOut } = useAuth();

  const onLogout = async () => {
    await signOut();
    navigate("/login", { replace: true });
  };

  return (
    <div className="mx-auto flex min-h-screen max-w-[480px] flex-col bg-cream">
      <header className="sticky top-0 z-10 flex h-14 items-center justify-between bg-cream/95 px-4 backdrop-blur">
        {sub ? (
          <>
            <button className="tap -ml-2 text-xl" onClick={() => navigate(-1)} aria-label="뒤로 가기">
              ‹
            </button>
            <h1 className="text-lg font-bold">{handle.title}</h1>
            <span className="w-11" />
          </>
        ) : (
          <>
            <Link to="/" className="text-lg font-bold text-leaf">
              다올
            </Link>
            <button className="tap text-[15px] text-ink-sub" onClick={onLogout}>
              로그아웃
            </button>
          </>
        )}
      </header>

      <main className={`flex-1 ${sub ? "pb-8" : "pb-24"}`}>
        <Outlet />
      </main>

      {!handle.hideChat && (
        <Link
          to="/chat"
          className={`fixed right-[max(16px,calc(50%-224px))] ${sub ? "bottom-6" : "bottom-24"} flex h-14 w-14 items-center justify-center rounded-full bg-leaf text-sm font-bold text-white shadow-lg`}
          aria-label="AI 복약 상담"
        >
          상담
        </Link>
      )}

      {!sub && (
        <nav className="fixed bottom-0 left-1/2 z-10 flex w-full max-w-[480px] -translate-x-1/2 items-center justify-around border-t border-line bg-white px-2 pb-[env(safe-area-inset-bottom)]">
          {TABS.map((t) => (
            <NavLink
              key={t.to}
              to={t.to}
              end={t.end}
              className={({ isActive }) =>
                t.center
                  ? "tap my-2 rounded-full bg-leaf px-4 py-2 text-[15px] font-bold text-white"
                  : `tap flex items-center justify-center px-2 text-[15px] ${isActive ? "font-bold text-leaf" : "text-ink-sub"}`
              }
            >
              {t.label}
            </NavLink>
          ))}
        </nav>
      )}
    </div>
  );
}
