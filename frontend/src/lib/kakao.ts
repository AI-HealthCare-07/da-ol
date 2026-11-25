// 카카오 로그인: 카카오 인가 페이지로 보냈다가 redirect_uri(/auth/kakao/callback)로 code를 받아 옵니다.
// redirect_uri는 백엔드 KAKAO_REDIRECT_URI, 카카오 개발자 콘솔 등록 값과 똑같아야 합니다.

const STATE_KEY = "daol_kakao_state";

export function goKakaoLogin() {
  const clientId = import.meta.env.VITE_KAKAO_CLIENT_ID;
  const redirectUri = import.meta.env.VITE_KAKAO_REDIRECT_URI;
  if (!clientId || !redirectUri) {
    alert("카카오 로그인 설정(.env.local)이 비어 있어요");
    return;
  }
  const state = crypto.randomUUID();
  try {
    sessionStorage.setItem(STATE_KEY, state); // 다른 사이트가 보낸 요청이 아닌지 확인용
  } catch {
    /* 저장 못 하는 환경이면 확인을 건너뜁니다 */
  }
  const url = new URL("https://kauth.kakao.com/oauth/authorize");
  url.search = new URLSearchParams({ client_id: clientId, redirect_uri: redirectUri, response_type: "code", state }).toString();
  window.location.href = url.toString();
}

export function checkKakaoState(state: string | null): boolean {
  try {
    const saved = sessionStorage.getItem(STATE_KEY);
    sessionStorage.removeItem(STATE_KEY);
    return saved === null || saved === state;
  } catch {
    return true;
  }
}
