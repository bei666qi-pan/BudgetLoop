import { defineConfig, devices } from "@playwright/test";

const baseURL = process.env.E2E_GENERATED_BASE_URL;
if (!baseURL) throw new Error("E2E_GENERATED_BASE_URL is required");

export default defineConfig({
  testDir: "./tests",
  outputDir: process.env.E2E_GENERATED_OUTPUT ?? "./test-results/generated-site",
  fullyParallel: false,
  retries: 0,
  workers: 1,
  timeout: 60_000,
  reporter: [["list"]],
  use: {
    baseURL,
    screenshot: "on",
    trace: "retain-on-failure",
  },
  projects: [
    { name: "desktop-1440", use: { ...devices["Desktop Chrome"], viewport: { width: 1440, height: 1000 } } },
    { name: "mobile-390", use: { ...devices["iPhone 13"], viewport: { width: 390, height: 844 } } },
  ],
});
