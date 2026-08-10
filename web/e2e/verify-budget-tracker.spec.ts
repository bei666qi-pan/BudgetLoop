import { expect, test } from "@playwright/test";

const PRODUCT_URL = process.env.PRODUCT_BASE_URL ?? "http://127.0.0.1:4173";
const DESKTOP_SHOT = "/Users/qi/Desktop/交付中心/budget-tracker-desktop.png";
const MOBILE_SHOT = "/Users/qi/Desktop/交付中心/budget-tracker-mobile-390.png";

test("预算追踪器通过真实 HTTP 桌面与 390px 端到端验收", async ({ page }) => {
  const consoleErrors: string[] = [];
  const failedRequests: string[] = [];
  const externalRequests: string[] = [];
  const origin = new URL(PRODUCT_URL).origin;

  page.on("console", (message) => {
    if (message.type() === "error") consoleErrors.push(message.text());
  });
  page.on("requestfailed", (request) => {
    failedRequests.push(`${request.method()} ${request.url()}: ${request.failure()?.errorText}`);
  });
  page.on("request", (request) => {
    const url = new URL(request.url());
    if (url.protocol.startsWith("http") && url.origin !== origin) externalRequests.push(request.url());
  });
  page.on("dialog", (dialog) => dialog.accept());

  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto(PRODUCT_URL, { waitUntil: "networkidle" });
  await page.evaluate(() => localStorage.clear());
  await page.reload({ waitUntil: "networkidle" });

  await expect(page.locator("h1")).toContainText("预算追踪器");
  await expect(page.locator("#balance")).toHaveText("¥0.00");

  await page.locator("#amountInput").fill("1000");
  await page.locator("#categoryInput").fill("工资");
  await page.locator("#noteInput").fill("八月收入");
  await page.locator("button[type=submit]").click();

  await page.locator("#amountInput").fill("-250");
  await page.locator("#categoryInput").fill("餐饮");
  await page.locator("#noteInput").fill("团队午餐");
  await page.locator("button[type=submit]").click();

  await expect(page.locator("#balance")).toHaveText("¥750.00");
  await expect(page.locator("#totalIncome")).toHaveText("¥1000.00");
  await expect(page.locator("#totalExpense")).toHaveText("¥250.00");
  await expect(page.locator("#categorySummary")).toContainText("工资");
  await expect(page.locator("#categorySummary")).toContainText("餐饮");

  await page.reload({ waitUntil: "networkidle" });
  await expect(page.locator("#transactionList")).toContainText("八月收入");
  await expect(page.locator("#transactionList")).toContainText("团队午餐");
  await expect(page.locator("#balance")).toHaveText("¥750.00");

  await page.locator("button[type=submit]").click();
  await expect(page.locator("#formError")).toBeVisible();
  await expect(page.locator("#formError")).toHaveText("请输入金额");
  await expect(page.locator("#amountInput")).toBeFocused();

  await page.locator("#amountInput").fill("50");
  await page.locator("#categoryInput").fill("奖金");
  await page.locator("#noteInput").fill("键盘提交");
  await page.locator("#noteInput").focus();
  await page.keyboard.press("Tab");
  await expect(page.locator("button[type=submit]")).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(page.locator("#transactionList")).toContainText("键盘提交");
  await expect(page.locator("#balance")).toHaveText("¥800.00");

  await page.screenshot({ path: DESKTOP_SHOT, fullPage: true });

  const beforeDelete = await page.locator("#transactionList tr").count();
  await page.locator(".delete-btn").first().click();
  await expect(page.locator("#transactionList tr")).toHaveCount(beforeDelete - 1);

  await page.setViewportSize({ width: 390, height: 844 });
  await page.reload({ waitUntil: "networkidle" });
  const dimensions = await page.evaluate(() => ({
    innerWidth: window.innerWidth,
    documentScrollWidth: document.documentElement.scrollWidth,
    bodyScrollWidth: document.body.scrollWidth,
  }));
  expect(dimensions.innerWidth).toBe(390);
  expect(dimensions.documentScrollWidth).toBeLessThanOrEqual(dimensions.innerWidth);
  expect(dimensions.bodyScrollWidth).toBeLessThanOrEqual(dimensions.innerWidth);
  await expect(page.locator("button[type=submit]")).toBeVisible();
  await page.screenshot({ path: MOBILE_SHOT, fullPage: true });

  expect(consoleErrors, `console errors: ${JSON.stringify(consoleErrors)}`).toEqual([]);
  expect(failedRequests, `failed requests: ${JSON.stringify(failedRequests)}`).toEqual([]);
  expect(externalRequests, `external requests: ${JSON.stringify(externalRequests)}`).toEqual([]);
});
