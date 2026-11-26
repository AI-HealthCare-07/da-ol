// 환경 변수에서 읽는 앱 전역 설정. 여러 슬라이스에서 쓰므로 shared에 둡니다.
export const USE_MOCK = import.meta.env.VITE_USE_MOCK === "true";
