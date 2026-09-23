import { defineConfig } from "@playwright/test";

// Run the compose stack first (docker compose up --build), then:
//   cd e2e && npm install && npx playwright install chromium && npm test
// WEB_URL overrides the target when not using the compose ports.
export default defineConfig({
  testDir: "./tests",
  retries: 0,
  use: {
    baseURL: process.env.WEB_URL || "http://localhost:8080",
  },
});
