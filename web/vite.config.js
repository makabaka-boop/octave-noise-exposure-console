import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The SPA calls the API on the same origin under /api. In dev and preview
// we proxy to a locally running API; in the Docker deployment nginx does
// the equivalent proxying (see web/nginx.conf).
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: { "/api": "http://localhost:8000" },
  },
  preview: {
    port: 4173,
    proxy: { "/api": "http://localhost:8000" },
  },
});
