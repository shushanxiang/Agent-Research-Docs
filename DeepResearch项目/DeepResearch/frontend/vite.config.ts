import path from "node:path";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react-swc";
import tailwindcss from "@tailwindcss/vite";

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  base: "/app/",
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    proxy: {
      // 将所有请求代理到 LangGraph runtime（含 FastAPI app + API server）
      // 统一使用同一个源，确保 Cookie 自动携带
      "/api": {
        target: "http://127.0.0.1:2024",
        changeOrigin: true,
      },
      "/threads": {
        target: "http://127.0.0.1:2024",
        changeOrigin: true,
      },
      "/runs": {
        target: "http://127.0.0.1:2024",
        changeOrigin: true,
      },
      "/assistants": {
        target: "http://127.0.0.1:2024",
        changeOrigin: true,
      },
    },
  },
});
