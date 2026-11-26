import { fileURLToPath, URL } from "node:url";
import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

// 로컬 개발: /api 요청을 백엔드(FastAPI)로 넘깁니다.
// 배포(Vercel)의 vercel.json rewrites와 같은 구조라, 프론트 코드는 항상 상대 경로 /api/v1/... 로 부릅니다.
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  return {
    plugins: [react(), tailwindcss()],
    resolve: {
      alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) },
    },
    server: {
      port: 5173,
      proxy: {
        "/api": { target: env.VITE_DEV_API_TARGET || "http://localhost:8000", changeOrigin: true },
      },
    },
  };
});