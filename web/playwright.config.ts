import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  timeout: 60000,
  expect: { timeout: 15000 },
  use: {
    baseURL: "http://localhost:3000",
    headless: true,
    viewport: { width: 1440, height: 900 },
    screenshot: "on",
    video: "retain-on-failure",
    trace: "on-first-retry",
  },
  outputDir: "test-results",
});
