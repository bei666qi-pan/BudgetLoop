import { expect, test } from "@playwright/test";

test("published Agent site is self-contained, usable, and responsive", async ({ page }) => {
  const consoleErrors: string[] = [];
  const failedRequests: string[] = [];
  const externalRequests: string[] = [];
  const allowedOrigin = new URL(process.env.E2E_GENERATED_BASE_URL!).origin;

  page.on("console", (message) => {
    if (message.type() === "error") consoleErrors.push(message.text());
  });
  page.on("request", (request) => {
    if (new URL(request.url()).origin !== allowedOrigin) externalRequests.push(request.url());
  });
  page.on("requestfailed", (request) => failedRequests.push(`${request.url()}: ${request.failure()?.errorText ?? "failed"}`));

  const response = await page.goto("/", { waitUntil: "networkidle" });
  expect(response?.ok()).toBeTruthy();
  await expect(page.locator("main")).toBeVisible();
  await expect(page.locator("h1")).toBeVisible();
  await expect(page.locator("h1")).not.toHaveText("");
  expect((await page.locator("body").innerText()).trim().length).toBeGreaterThan(300);
  expect(await page.locator("main section, main article").count()).toBeGreaterThanOrEqual(2);
  expect(await page.locator("a[href], button").count()).toBeGreaterThanOrEqual(1);

  const images = page.locator("img");
  for (let index = 0; index < await images.count(); index += 1) {
    expect((await images.nth(index).getAttribute("alt"))?.trim().length ?? 0).toBeGreaterThan(0);
  }

  await page.keyboard.press("Tab");
  await expect.poll(() => page.evaluate(() => document.activeElement?.tagName ?? "BODY")).not.toBe("BODY");
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  expect(overflow).toBeLessThanOrEqual(1);
  expect(consoleErrors).toEqual([]);
  expect(failedRequests).toEqual([]);
  expect(externalRequests).toEqual([]);
  await page.screenshot({ path: `test-results/${process.env.E2E_GENERATED_MARKER}-${test.info().project.name}.png`, fullPage: true });
});
