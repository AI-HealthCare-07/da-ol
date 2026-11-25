import { api } from "./client";
import type { HomeResponse, IntakePatchResponse, IntakeStatus } from "./types";
import { mockHome } from "./mock";

export const USE_MOCK = import.meta.env.VITE_USE_MOCK === "true";

export function getHome(date?: string): Promise<HomeResponse> {
  if (USE_MOCK) return Promise.resolve(structuredClone(mockHome));
  return api<HomeResponse>(`/home${date ? `?date=${date}` : ""}`);
}

// 약 하나(복용 기록 한 줄) 체크·취소
export function patchIntake(intakeId: number, status: Extract<IntakeStatus, "taken" | "pending">) {
  if (USE_MOCK) {
    return Promise.resolve({
      intake_id: intakeId,
      status,
      taken_at: status === "taken" ? new Date().toISOString() : null,
      day_summary: { log_date: mockHome.date, done_count: 0, total_count: 0 }, // 가짜 모드는 화면에서 다시 셉니다
      flower: { bloomed: false, just_bloomed: false },
    } satisfies IntakePatchResponse);
  }
  return api<IntakePatchResponse>(`/intakes/${intakeId}`, { method: "PATCH", body: { status } });
}

// 칸 전체 체크: 동시에 보내면 꽃 판단이 어긋날 수 있어 하나씩 순서대로 보냅니다.
export async function patchIntakesInOrder(intakeIds: number[], status: "taken" | "pending") {
  let last: IntakePatchResponse | undefined;
  for (const id of intakeIds) last = await patchIntake(id, status);
  return last;
}
