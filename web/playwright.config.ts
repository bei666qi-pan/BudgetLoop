import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  timeout: 60000,
  expect: { timeout: 15000 },
  use: {
    baseURL: "http://localhost:3000",
    headless: false,  // 真实浏览器可见
    viewport: { width: 1440, height: 900 },
    screenshot: "on",
    video: "retain-on-failure",
    trace: "on-first-retry",
  },
  outputDir: "test-results",
});
