import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Dev server proxies /api to Django so there is no CORS to configure.
export default defineConfig({
  plugins: [react()],
  server: { proxy: { "/api": "http://127.0.0.1:8000" } },
});
