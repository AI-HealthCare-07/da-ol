import type { HomeResponse, HomeSlotItem } from "./types";

// 홈 3D 시안(v16)과 같은 예시: 아침·점심·저녁 다올정, 점심에 4개 더, 취침 전 새싹캡슐
let nextId = 3000;
const item = (drug: string, dose: string, label: string, taken: boolean): HomeSlotItem => ({
  intake_id: nextId++,
  prescription_id: 512,
  prescription_item_id: 1300 + nextId,
  drug_name: drug,
  dose_text: dose,
  condition_label: label,
  status: taken ? "taken" : "pending",
  taken_at: null,
});

export const mockHome: HomeResponse = {
  date: "2026-11-20",
  is_today: true,
  is_editable: true,
  uses_default_routine: true,
  has_active_prescription: true,
  week: [
    { date: "2026-11-14", done_count: 0, total_count: 0, bloomed: false },
    { date: "2026-11-15", done_count: 0, total_count: 0, bloomed: false },
    { date: "2026-11-16", done_count: 0, total_count: 0, bloomed: false },
    { date: "2026-11-17", done_count: 8, total_count: 8, bloomed: true },
    { date: "2026-11-18", done_count: 6, total_count: 8, bloomed: false },
    { date: "2026-11-19", done_count: 8, total_count: 8, bloomed: true },
    { date: "2026-11-20", done_count: 2, total_count: 8, bloomed: false },
  ],
  day_summary: { log_date: "2026-11-20", done_count: 2, total_count: 8 },
  flower: { bloomed: false },
  next_dose: { scheduled_time: "19:00", slot_label: "저녁" },
  slots: [
    { scheduled_time: "08:30", slot_label: "아침", slot_status: "done", items: [item("다올정 10mg", "1정", "아침 식후 30분", true)] },
    {
      scheduled_time: "13:00",
      slot_label: "점심",
      slot_status: "late",
      items: [
        item("다올정 10mg", "1정", "점심 식후 30분", true),
        item("물방울정 500mg", "1정", "점심 식후 30분", false),
        item("햇살정 5mg", "1정", "점심 식후 30분", false),
        item("구름정 20mg", "1정", "점심 식후 30분", false),
        item("바람정 100mg", "0.5정", "점심 식후 30분", false),
      ],
    },
    { scheduled_time: "19:00", slot_label: "저녁", slot_status: "due", items: [item("다올정 10mg", "1정", "저녁 식후 30분", false)] },
    { scheduled_time: "23:00", slot_label: "취침 전", slot_status: "due", items: [item("새싹캡슐", "1캡슐", "취침 전", false)] },
  ],
  as_needed_items: [],
  schedule_check_items: [],
  generating_guides: [],
};
