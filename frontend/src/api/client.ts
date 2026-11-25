// 모든 API 호출이 지나가는 함수 하나.
// - 액세스 토큰은 메모리에만 둡니다 (localStorage 저장 금지, 명세 4-1).
// - 리프레시 토큰은 HttpOnly 쿠키라 프론트가 만지지 않습니다. Vercel rewrites로 같은 주소처럼 써서 쿠키가 따라갑니다.
// - 401을 받으면 재발급을 한 번 하고 원래 요청을 다시 보냅니다.
//   여러 요청이 동시에 401을 받아도 재발급은 한 번만 부릅니다(single-flight). 회전 방식이라 두 번 부르면 두 번째가 실패합니다.

export interface ApiErrorBody {
  code: string;
  message: string;
  fields?: Record<string, string>;
}

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly fields?: Record<string, string>;
  constructor(status: number, body: ApiErrorBody) {
    super(body.message);
    this.status = status;
    this.code = body.code;
    this.fields = body.fields;
  }
}

const BASE = "/api/v1";

let accessToken: string | null = null;
export const getAccessToken = () => accessToken;
export const setAccessToken = (token: string | null) => {
  accessToken = token;
};

// 로그인 만료·추가 정보 필요 시 화면 이동은 AuthProvider가 등록합니다.
let onSessionExpired: () => void = () => {};
let onProfileRequired: () => void = () => {};
export function setAuthHandlers(handlers: { onSessionExpired: () => void; onProfileRequired: () => void }) {
  onSessionExpired = handlers.onSessionExpired;
  onProfileRequired = handlers.onProfileRequired;
}

async function toApiError(res: Response): Promise<ApiError> {
  try {
    const body = (await res.json()) as ApiErrorBody;
    if (body && typeof body.code === "string") return new ApiError(res.status, body);
  } catch {
    /* 본문이 JSON이 아닐 때 */
  }
  return new ApiError(res.status, { code: "INTERNAL_ERROR", message: "잠시 후 다시 시도해 주세요" });
}

let refreshPromise: Promise<string> | null = null;
export function refreshAccessToken(): Promise<string> {
  if (!refreshPromise) {
    refreshPromise = (async () => {
      const res = await fetch(`${BASE}/auth/refresh`, { method: "POST" });
      if (!res.ok) throw await toApiError(res);
      const data = (await res.json()) as { access_token: string };
      setAccessToken(data.access_token);
      return data.access_token;
    })().finally(() => {
      refreshPromise = null;
    });
  }
  return refreshPromise;
}

interface RequestOptions {
  method?: "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
  body?: unknown; // 객체면 JSON, FormData면 그대로
  auth?: boolean; // 기본 true
  signal?: AbortSignal;
}

export async function api<T>(path: string, opts: RequestOptions = {}, retried = false): Promise<T> {
  const { method = "GET", body, auth = true, signal } = opts;
  const headers: Record<string, string> = {};
  if (auth && accessToken) headers.Authorization = `Bearer ${accessToken}`;
  let payload: BodyInit | undefined;
  if (body instanceof FormData) payload = body;
  else if (body !== undefined) {
    headers["Content-Type"] = "application/json";
    payload = JSON.stringify(body);
  }

  const res = await fetch(`${BASE}${path}`, { method, headers, body: payload, signal });

  if (res.status === 401 && auth && !retried) {
    try {
      await refreshAccessToken();
    } catch {
      setAccessToken(null);
      onSessionExpired();
      throw new ApiError(401, { code: "REFRESH_TOKEN_EXPIRED", message: "로그인이 만료되었습니다" });
    }
    return api<T>(path, opts, true);
  }
  if (!res.ok) {
    const err = await toApiError(res);
    if (err.code === "PROFILE_REQUIRED") onProfileRequired();
    throw err;
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}
