import { useState } from "react";
import { useNavigate } from "react-router";
import { saveProfile, type ConsentType } from "../api/auth";
import { ApiError } from "../api/client";
import { USE_MOCK } from "../api/home";
import { useAuth } from "../auth/AuthProvider";
import { ageOn, isValidDate, todayKST } from "../lib/date";

// A-1-2 추가 정보 입력 + 약관 동의 (REQ-USER-002, 명세 4장 POST /users/me/profile)
// - 이름·생년월일·성별은 나중에 바꿀 수 없어서(REQ-USER-009) 저장 전에 한 번 더 보여 줍니다.
// - 만 14세 미만은 1차에서 가입을 막습니다(명세 4-9 13).

const CONSENTS: { type: ConsentType; label: string; body: string }[] = [
  { type: "terms", label: "서비스 이용약관", body: "서비스 이용약관 전문은 확정되면 넣을 예정이에요." },
  { type: "privacy", label: "개인정보 수집·이용", body: "수집 항목: 이름, 생년월일, 성별, 카카오 회원번호, 이메일(동의한 경우)\n이용 목적: 회원 식별, 복약 안내 제공\n보관 기간: 탈퇴 후 30일" },
  { type: "sensitive_health", label: "민감정보(건강정보) 수집·이용", body: "수집 항목: 처방 정보, 복용 기록, 건강 프로필(기저질환 등)\n이용 목적: 복약 안내·생활 습관 가이드 생성\n보관 기간: 탈퇴 후 30일" },
];

type Gender = "male" | "female";

export default function ProfileSetupPage() {
  const navigate = useNavigate();
  const { applyMe, me } = useAuth();
  const [name, setName] = useState("");
  const [birth, setBirth] = useState("");
  const [gender, setGender] = useState<Gender | null>(null);
  const [agreed, setAgreed] = useState<Record<ConsentType, boolean>>({ terms: false, privacy: false, sensitive_health: false });
  const [viewing, setViewing] = useState<(typeof CONSENTS)[number] | null>(null);
  const [confirming, setConfirming] = useState(false);
  const [saving, setSaving] = useState(false);
  const [serverErrors, setServerErrors] = useState<Record<string, string>>({});

  const today = todayKST();
  const trimmed = name.trim();
  const nameError = name && (trimmed.length < 1 || trimmed.length > 20) ? "이름은 1~20자로 적어 주세요" : "";
  let birthError = "";
  if (birth) {
    if (!isValidDate(birth) || birth < "1900-01-01" || birth > today) birthError = "생년월일을 다시 확인해 주세요";
    else if (ageOn(birth, today) < 14) birthError = "만 14세 이상만 가입할 수 있어요";
  }
  const allAgreed = CONSENTS.every((c) => agreed[c.type]);
  const canSubmit = trimmed.length >= 1 && !nameError && birth && !birthError && gender && allAgreed && !saving;

  const toggleAll = () => {
    const v = !allAgreed;
    setAgreed({ terms: v, privacy: v, sensitive_health: v });
  };

  const submit = async () => {
    if (!canSubmit || !gender) return;
    setSaving(true);
    setServerErrors({});
    const body = {
      name: trimmed,
      birth_date: birth,
      gender,
      consents: CONSENTS.map((c) => ({ consent_type: c.type, agreed: true })),
    };
    try {
      const saved = USE_MOCK
        ? { ...me!, name: trimmed, birth_date: birth, gender, is_profile_completed: true }
        : await saveProfile(body);
      applyMe(saved);
      void navigate("/", { replace: true });
    } catch (e) {
      setConfirming(false);
      if (e instanceof ApiError && e.code === "PROFILE_ALREADY_COMPLETED") {
        void navigate("/", { replace: true });
      } else if (e instanceof ApiError && e.fields) {
        setServerErrors(e.fields);
      } else {
        alert(e instanceof ApiError ? e.message : "저장하지 못했어요. 다시 시도해 주세요");
      }
    } finally {
      setSaving(false);
    }
  };

  const field = "tap w-full rounded-xl border-[1.5px] border-line bg-white px-4 text-lg outline-none focus:border-leaf";
  const err = (msg?: string) => (msg ? <p className="mt-1.5 text-[15px] text-[#c0502a]">{msg}</p> : null);

  return (
    <div className="mx-auto flex min-h-screen max-w-[480px] flex-col bg-cream">
      <div className="flex-1 px-5 pt-10 pb-32">
        <h1 className="text-2xl font-bold">처음 오셨네요</h1>
        <p className="mt-2 text-ink-sub">복약 안내에 필요한 정보를 알려 주세요.</p>

        <label className="mt-8 block">
          <span className="mb-2 block font-bold">이름</span>
          <input className={field} value={name} maxLength={20} autoComplete="name" onChange={(e) => setName(e.target.value)} placeholder="예: 김다올" />
          {err(nameError || serverErrors.name)}
        </label>

        <label className="mt-6 block">
          <span className="mb-2 block font-bold">생년월일</span>
          <input className={field} type="date" min="1900-01-01" max={today} value={birth} onChange={(e) => setBirth(e.target.value)} />
          {err(birthError || serverErrors.birth_date)}
        </label>

        <fieldset className="mt-6">
          <legend className="mb-2 font-bold">성별</legend>
          <div className="grid grid-cols-2 gap-3">
            {(["female", "male"] as const).map((g) => (
              <button
                key={g}
                type="button"
                onClick={() => setGender(g)}
                aria-pressed={gender === g}
                className={`tap rounded-xl border-[1.5px] text-lg ${gender === g ? "border-leaf bg-leaf-soft font-bold text-leaf" : "border-line bg-white"}`}
              >
                {g === "female" ? "여성" : "남성"}
              </button>
            ))}
          </div>
          {err(serverErrors.gender)}
        </fieldset>

        <section className="mt-8 rounded-2xl bg-white p-2">
          <button type="button" onClick={toggleAll} className="tap flex w-full items-center gap-3 rounded-xl px-3 text-left text-lg font-bold">
            <Check on={allAgreed} /> 전체 동의
          </button>
          <div className="mx-3 my-1 border-t border-line" />
          {CONSENTS.map((c) => (
            <div key={c.type} className="flex items-center">
              <button
                type="button"
                onClick={() => setAgreed((a) => ({ ...a, [c.type]: !a[c.type] }))}
                className="tap flex flex-1 items-center gap-3 px-3 text-left text-[16px]"
              >
                <Check on={agreed[c.type]} />
                <span>
                  {c.label} <span className="text-sun-ink">(필수)</span>
                </span>
              </button>
              <button type="button" onClick={() => setViewing(c)} className="tap px-3 text-[15px] text-ink-sub underline">
                보기
              </button>
            </div>
          ))}
          {err(serverErrors.consents)}
        </section>
      </div>

      <div className="fixed bottom-0 left-1/2 w-full max-w-[480px] -translate-x-1/2 bg-cream px-5 pt-3 pb-[max(16px,env(safe-area-inset-bottom))]">
        <button
          onClick={() => setConfirming(true)}
          disabled={!canSubmit}
          className="tap w-full rounded-2xl bg-leaf py-4 text-lg font-bold text-white disabled:bg-[#cfd8c8]"
        >
          시작하기
        </button>
      </div>

      {viewing && (
        <Modal title={viewing.label} onClose={() => setViewing(null)}>
          <p className="whitespace-pre-line text-[16px] leading-7 text-ink">{viewing.body}</p>
          <button onClick={() => setViewing(null)} className="tap mt-5 w-full rounded-xl bg-leaf py-3 font-bold text-white">
            확인
          </button>
        </Modal>
      )}

      {confirming && gender && (
        <Modal title="이대로 저장할까요?" onClose={() => setConfirming(false)}>
          <p className="text-ink-sub">이름·생년월일·성별은 저장한 뒤에 바꿀 수 없어요.</p>
          <dl className="mt-4 grid grid-cols-[80px_1fr] gap-y-2 text-lg">
            <dt className="text-ink-sub">이름</dt>
            <dd className="font-bold">{trimmed}</dd>
            <dt className="text-ink-sub">생년월일</dt>
            <dd className="font-bold">{birth.replaceAll("-", ". ")}</dd>
            <dt className="text-ink-sub">성별</dt>
            <dd className="font-bold">{gender === "female" ? "여성" : "남성"}</dd>
          </dl>
          <div className="mt-6 grid grid-cols-2 gap-3">
            <button onClick={() => setConfirming(false)} className="tap rounded-xl bg-[#efe9de] py-3 font-bold">
              고칠래요
            </button>
            <button onClick={submit} disabled={saving} className="tap rounded-xl bg-leaf py-3 font-bold text-white">
              {saving ? "저장 중…" : "저장하기"}
            </button>
          </div>
        </Modal>
      )}
    </div>
  );
}

function Check({ on }: { on: boolean }) {
  return (
    <span
      aria-hidden
      className={`flex h-7 w-7 flex-none items-center justify-center rounded-full border-2 text-[15px] font-bold text-white ${on ? "border-leaf bg-leaf" : "border-line bg-white"}`}
    >
      {on ? "✓" : ""}
    </span>
  );
}

function Modal({ title, children, onClose }: { title: string; children: React.ReactNode; onClose: () => void }) {
  return (
    <div className="fixed inset-0 z-20 flex items-end justify-center bg-black/30 sm:items-center" onClick={onClose}>
      <div role="dialog" aria-modal="true" aria-label={title} className="w-full max-w-[480px] rounded-t-3xl bg-white p-6 sm:rounded-3xl" onClick={(e) => e.stopPropagation()}>
        <h2 className="mb-3 text-xl font-bold">{title}</h2>
        {children}
      </div>
    </div>
  );
}
