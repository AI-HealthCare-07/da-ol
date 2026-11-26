// API 명세(docs/planning/daol_API_명세서.md) 응답 모양. 칸 이름은 명세와 똑같이 씁니다.

export interface Me {
  user_id: number;
  nickname: string;
  email: string | null;
  name: string | null;
  birth_date: string | null;
  gender: "male" | "female" | null;
  is_profile_completed: boolean;
  created_at: string;
}

export interface KakaoLoginResponse {
  access_token: string;
  token_type: "Bearer";
  expires_in: number;
  is_new_user: boolean;
  is_profile_completed: boolean;
  user: { user_id: number; nickname: string };
}

// ---- 5장 GET /home?date= ----
export type IntakeStatus = "pending" | "taken" | "missed";
export type SlotStatus = "done" | "due" | "late";

export interface HomeSlotItem {
  intake_id: number;
  prescription_id: number;
  prescription_item_id: number;
  drug_name: string;
  dose_text: string;
  condition_label: string;
  status: IntakeStatus;
  taken_at: string | null;
}

export interface HomeSlot {
  scheduled_time: string; // "08:30"
  slot_label: string | null; // 아침 / 점심 / 저녁 / 취침 전 / null(섞임)
  slot_status: SlotStatus;
  items: HomeSlotItem[];
}

export interface DaySummary {
  log_date: string;
  done_count: number;
  total_count: number;
}

export interface HomeResponse {
  date: string;
  is_today: boolean;
  is_editable: boolean;
  uses_default_routine: boolean;
  has_active_prescription: boolean;
  week: { date: string; done_count: number; total_count: number; bloomed: boolean }[];
  day_summary: DaySummary;
  flower: { bloomed: boolean };
  next_dose: { scheduled_time: string; slot_label: string | null } | null;
  slots: HomeSlot[];
  as_needed_items: { prescription_item_id: number; drug_name: string; dose_text: string; condition_summary: string }[];
  schedule_check_items: unknown[];
  generating_guides: { prescription_id: number; hospital_name: string | null }[];
}

// ---- 4장 PATCH /intakes/{intake_id} ----
export interface IntakePatchResponse {
  intake_id: number;
  status: IntakeStatus;
  taken_at: string | null;
  day_summary: DaySummary;
  flower: { bloomed: boolean; just_bloomed: boolean };
}
