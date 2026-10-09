import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const api = "http://127.0.0.1:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    host: "0.0.0.0",
    port: 5173,
    strictPort: true,
    proxy: {
      "/proposals": { target: api, changeOrigin: true },
      "/reviews": { target: api, changeOrigin: true },
      "/approvals": { target: api, changeOrigin: true },
      "/audit": { target: api, changeOrigin: true },
      "/gaps": { target: api, changeOrigin: true },
      "/demo": { target: api, changeOrigin: true },
      "/catalog": { target: api, changeOrigin: true },
    },
  },
});
