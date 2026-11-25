import { lazy, Suspense, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router";
// three.js가 커서 홈에서만 따로 불러옵니다
const PillBox3D = lazy(() => import("../components/home/PillBox3D"));
import { getHome, patchIntake, patchIntakesInOrder, USE_MOCK } from "../api/home";
import type { HomeResponse, HomeSlot } from "../api/types";

// A-2 홈: 회전 약통(3D) + 회차 버튼 + 지금 칸 카드 + 그 회차 약 목록
// 저장은 약 하나씩(PATCH /intakes/{intake_id}), 칸은 안의 약을 다 먹어야 완료 → 통이 돌아감

const slotName = (s: HomeSlot) => s.slot_label ?? s.scheduled_time;
const slotDoneOf = (s: HomeSlot) => s.items.every((i) => i.status === "taken");
const WEEKDAYS = ["일", "월", "화", "수", "목", "금", "토"];

export default function HomePage() {
  const [home, setHome] = useState<HomeResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [current, setCurrent] = useState(0);
  const [rotate, setRotate] = useState<"advance" | "nearest">("nearest");
  const [saving, setSaving] = useState(false);
  const advanceTimer = useRef<number | undefined>(undefined);

  useEffect(() => {
    getHome()
      .then((h) => {
        setHome(h);
        const first = h.slots.findIndex((s) => !slotDoneOf(s));
        setCurrent(first < 0 ? h.slots.length : first);
      })
      .catch(() => setError("홈 정보를 불러오지 못했어요. 잠시 후 다시 시도해 주세요"));
    return () => window.clearTimeout(advanceTimer.current);
  }, []);

  const slots = home?.slots ?? [];
  const DONE = slots.length; // 빈 판 자리
  const slotDone = useMemo(() => slots.map(slotDoneOf), [slots]);
  const doneCount = slotDone.filter(Boolean).length;
  const allDone = slots.length > 0 && doneCount === slots.length;
  const editable = home?.is_editable ?? false;

  const goTo = useCallback((k: number) => {
    setRotate("nearest");
    setCurrent(k);
  }, []);

  // 칸을 다 먹은 뒤: 다음 안 먹은 칸(없으면 빈 판)으로 한 방향 회전
  const advanceFrom = useCallback((from: number, doneNow: boolean[]) => {
    window.clearTimeout(advanceTimer.current);
    advanceTimer.current = window.setTimeout(() => {
      const n = doneNow.length;
      let next = n;
      for (let i = 1; i <= n; i++) {
        const k = (from + i) % n;
        if (!doneNow[k]) { next = k; break; }
      }
      setRotate("advance");
      setCurrent(next);
    }, 650);
  }, []);

  // 화면 데이터에서 기록 상태만 바꾸기 (+ 실제 API면 응답의 개수·꽃 반영)
  const applyStatus = (ids: number[], status: "taken" | "pending", summary?: Partial<HomeResponse>) =>
    setHome((h) =>
      h && {
        ...h,
        ...summary,
        slots: h.slots.map((s) => ({
          ...s,
          items: s.items.map((i) =>
            ids.includes(i.intake_id) ? { ...i, status, taken_at: status === "taken" ? new Date().toISOString() : null } : i,
          ),
        })),
      },
    );

  // 목록에서 약 하나 체크·취소
  const toggleItem = async (k: number, intakeId: number) => {
    if (!home || !editable || saving) return;
    const item = slots[k].items.find((i) => i.intake_id === intakeId)!;
    const next = item.status === "taken" ? "pending" : "taken";
    const wasDone = slotDone[k];
    if (k !== current) goTo(k);
    applyStatus([intakeId], next); // 먼저 화면을 바꾸고
    try {
      const res = await patchIntake(intakeId, next);
      if (!USE_MOCK) applyStatus([intakeId], next, { day_summary: res.day_summary, flower: { bloomed: res.flower.bloomed } });
      const nowDone = slots[k].items.every((i) => (i.intake_id === intakeId ? next === "taken" : i.status === "taken"));
      if (!wasDone && nowDone) advanceFrom(k, slotDone.map((d, i) => (i === k ? true : d)));
    } catch {
      applyStatus([intakeId], item.status === "taken" ? "taken" : "pending"); // 실패하면 되돌리기
      alert("저장하지 못했어요. 다시 눌러 주세요");
    }
  };

  // [먹었어요] / [체크 취소]: 칸 안 약 전체. 동시에 보내면 꽃 판단이 어긋날 수 있어 하나씩 순서대로
  const toggleSlot = async () => {
    if (current === DONE || !editable || saving) return;
    const s = slots[current];
    const done = slotDone[current];
    const ids = s.items.filter((i) => (done ? i.status === "taken" : i.status !== "taken")).map((i) => i.intake_id);
    setSaving(true);
    try {
      const res = await patchIntakesInOrder(ids, done ? "pending" : "taken");
      applyStatus(ids, done ? "pending" : "taken", !USE_MOCK && res ? { day_summary: res.day_summary, flower: { bloomed: res.flower.bloomed } } : undefined);
      if (!done) advanceFrom(current, slotDone.map((d, i) => (i === current ? true : d)));
    } catch {
      alert("저장하지 못했어요. 다시 눌러 주세요");
      getHome().then(setHome).catch(() => {}); // 중간까지 저장됐을 수 있어 다시 불러오기
    } finally {
      setSaving(false);
    }
  };

  const onPressBox = useCallback(() => {
    if (current !== DONE && !slotDone[current]) void toggleSlot();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [current, DONE, slotDone, saving, editable, home]);

  if (error) return <p className="px-5 py-10 text-center text-ink-sub">{error}</p>;
  if (!home) return <p className="px-5 py-10 text-center text-ink-sub">불러오는 중…</p>;

  if (!home.has_active_prescription || slots.length === 0) {
    return (
      <div className="px-6 py-16 text-center">
        <p className="text-lg">처방전을 찍어 약을 등록해 보세요</p>
        <Link to="/register" className="tap mt-6 inline-flex items-center rounded-2xl bg-leaf px-6 py-3 text-lg font-bold text-white">
          처방 등록하기
        </Link>
      </div>
    );
  }

  const cur = current === DONE ? null : slots[current];
  const curDone = current !== DONE && slotDone[current];
  const d = new Date(`${home.date}T00:00:00+09:00`);

  return (
    <div className="pb-6">
      {home.generating_guides.length > 0 && (
        <Link to={`/guides/${home.generating_guides[0].prescription_id}`} className="mx-5 mb-2 block rounded-xl bg-white px-4 py-3 text-[15px] shadow-sm">
          약통에 새 약이 들어갔어요 · 가이드를 만들고 있어요 ›
        </Link>
      )}

      <section className="px-5">
        <p className="text-ink-sub">
          {d.getMonth() + 1}월 {d.getDate()}일 {WEEKDAYS[d.getDay()]}요일
        </p>
        <h2 className="mt-1 text-[28px] font-bold">
          {allDone ? (
            <span className="text-leaf">오늘 약을 다 먹었어요</span>
          ) : (
            <>
              {slots.length}번 중 <span className="text-leaf">{doneCount}번</span> 완료
            </>
          )}
        </h2>
        {/* 요일 미니 약통: 오늘 포함 7일 */}
        <div className="mt-3 flex justify-between">
          {home.week.map((w) => {
            const wd = new Date(`${w.date}T00:00:00+09:00`);
            const ratio = w.total_count ? w.done_count / w.total_count : 0;
            return (
              <div key={w.date} className="flex flex-col items-center gap-1 text-[13px] text-ink-sub">
                {WEEKDAYS[wd.getDay()]}
                <span
                  className={`h-7 w-7 rounded-full border-2 ${w.date === home.date ? "border-sun" : "border-line"}`}
                  style={{ background: w.bloomed ? "#8dbb78" : `conic-gradient(#f4c24d ${ratio * 360}deg, #fff 0)` }}
                />
              </div>
            );
          })}
        </div>
      </section>

      <Suspense fallback={<div className="aspect-[10/9] w-full" />}>
      <PillBox3D
        slotDone={slotDone}
        current={current}
        rotate={rotate}
        onPress={onPressBox}
        label={allDone ? "오늘 약을 다 먹은 약통" : `${cur ? slotName(cur) : ""} 칸이 열린 약통`}
      />
      </Suspense>

      {/* 회차 버튼 */}
      <div className="flex flex-wrap justify-center gap-2 px-4">
        {slots.map((s, k) => (
          <button
            key={s.scheduled_time}
            onClick={() => goTo(k)}
            className={`tap rounded-full border-[1.5px] px-4 text-[15px] ${
              slotDone[k] ? "border-[#cfe0c5] bg-leaf-soft text-leaf" : "border-line bg-white"
            } ${k === current ? "border-sun font-bold ring-2 ring-sun/20" : ""}`}
          >
            {slotDone[k] ? "✓ " : ""}
            {slotName(s)}
          </button>
        ))}
      </div>

      {/* 지금 칸 카드 */}
      <section className="mx-5 mt-4 rounded-2xl bg-white p-4 shadow-sm">
        {cur ? (
          <>
            <p className="text-xl font-bold">
              {slotName(cur)} {cur.scheduled_time}
              {cur.slot_status === "late" && !curDone && <span className="ml-2 align-middle text-sm font-bold text-sun-ink">시간 지남</span>}
            </p>
            <p className="mt-1.5 mb-3.5 text-ink-sub">
              {cur.items.length <= 3
                ? cur.items.map((i) => `${i.drug_name} ${i.dose_text}`).join(", ")
                : `${cur.items[0].drug_name} 외 ${cur.items.length - 1}개`}
              {" · "}
              {cur.items[0]?.condition_label}
            </p>
            {editable && (
              <button
                onClick={toggleSlot}
                disabled={saving}
                className={`tap w-full rounded-xl py-3.5 text-lg font-bold ${curDone ? "bg-[#efe9de] text-ink" : "bg-leaf text-white"}`}
              >
                {saving ? "저장 중…" : curDone ? "체크 취소" : "먹었어요"}
              </button>
            )}
          </>
        ) : (
          <>
            <p className="text-xl font-bold">{allDone ? "오늘 복용 완료" : "남은 약이 있어요"}</p>
            {allDone && <p className="mt-1.5 text-ink-sub">꽃이 피었어요. 내일도 함께해요.</p>}
          </>
        )}
      </section>

      {/* 고른 회차의 약 목록 (빈 판일 때는 전체) */}
      <h3 className="mx-5 mt-6 mb-2 text-lg font-bold">{cur ? `${slotName(cur)} 약` : "오늘 먹은 약"}</h3>
      {slots.map((s, k) => {
        if (cur && k !== current) return null;
        const n = s.items.filter((i) => i.status === "taken").length;
        return (
          <section key={s.scheduled_time} className="mx-5 mb-3 rounded-2xl bg-white p-3 shadow-sm">
            <p className="mx-1 mb-2 flex items-baseline gap-1 text-[15px] text-ink-sub">
              <b className="text-base text-ink">{slotName(s)}</b> {s.scheduled_time}
              <span className={`ml-auto text-sm font-bold ${n === s.items.length ? "text-leaf" : "text-sun-ink"}`}>
                {s.items.length}개 중 {n}개
              </span>
            </p>
            {s.items.map((it) => {
              const on = it.status === "taken";
              return (
                <button
                  key={it.intake_id}
                  onClick={() => toggleItem(k, it.intake_id)}
                  disabled={!editable}
                  className={`mt-1.5 flex min-h-[52px] w-full items-center gap-3 rounded-xl px-3 text-left ${on ? "bg-leaf-soft" : "bg-[#faf6ee]"}`}
                >
                  <span className="h-3.5 w-7 flex-none rounded-full" style={{ background: "linear-gradient(90deg,#8dbb78 50%,#f4c24d 50%)" }} />
                  <span className="flex-1">
                    {it.drug_name}
                    <small className="ml-1.5 text-[15px] text-ink-sub">{it.dose_text}</small>
                  </span>
                  <span
                    className={`flex h-[30px] w-[30px] items-center justify-center rounded-full border-2 font-bold text-white ${
                      on ? "border-leaf bg-leaf" : "border-line"
                    }`}
                    aria-label={on ? "먹음" : "안 먹음"}
                  >
                    {on ? "✓" : ""}
                  </span>
                </button>
              );
            })}
          </section>
        );
      })}

      {home.uses_default_routine && (
        <p className="mx-5 mt-4 rounded-xl bg-white px-4 py-3 text-[14px] text-ink-sub">
          기본 일과(기상 07:00 · 식사 08:00·12:30·18:30 · 취침 23:00)로 계산 중이에요
        </p>
      )}
    </div>
  );
}
