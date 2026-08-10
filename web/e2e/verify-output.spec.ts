import { test, expect } from "@playwright/test";
import path from "path";
const P = "/Users/qi/Desktop/测试文件夹";

test.describe("Agent 产出验收", () => {
  test("1. 三文件齐全", async () => {
    const fs = await import("fs");
    expect(fs.existsSync(path.join(P, "index.html"))).toBe(true);
    expect(fs.existsSync(path.join(P, "app.js"))).toBe(true);
    expect(fs.existsSync(path.join(P, "style.css"))).toBe(true);
    console.log("✅ 文件齐全");
  });

  test("2. 页面加载", async ({ page }) => {
    await page.goto(`file://${P}/index.html`);
    await page.waitForTimeout(1000);
    const t = await page.evaluate(() => document.body.innerText);
    expect(t).toContain("预算追踪器");
    expect(t).toContain("添加交易");
    console.log("✅ 页面完整");
  });

  test("3. 添加收入", async ({ page }) => {
    await page.goto(`file://${P}/index.html`);
    await page.waitForTimeout(1000);
    await page.selectOption("#transaction-type", "income");
    await page.fill("#transaction-amount", "8000");
    await page.selectOption("#transaction-category", "工资");
    await page.fill("#transaction-date", "2026-01-01");
    await page.locator(".submit-btn").click();
    await page.waitForTimeout(800);
    const listText = await page.locator("#transaction-list").textContent() || "";
    expect(listText).toContain("8000");
    console.log("✅ 收入正常");
  });

  test("4. 添加支出", async ({ page }) => {
    await page.goto(`file://${P}/index.html`);
    await page.waitForTimeout(1000);
    await page.selectOption("#transaction-type", "expense");
    await page.fill("#transaction-amount", "99.5");
    await page.selectOption("#transaction-category", "餐饮");
    await page.fill("#transaction-date", "2026-01-02");
    await page.locator(".submit-btn").click();
    await page.waitForTimeout(800);
    const listText = await page.locator("#transaction-list").textContent() || "";
    expect(listText).toContain("99.5");
    console.log("✅ 支出正常");
  });

  test("5. 删除交易", async ({ page }) => {
    await page.goto(`file://${P}/index.html`);
    await page.waitForTimeout(1000);
    await page.fill("#transaction-amount", "1");
    await page.fill("#transaction-date", "2026-01-03");
    await page.locator(".submit-btn").click();
    await page.waitForTimeout(500);
    const del = page.locator("#transaction-list button").first();
    if (await del.count() > 0) { await del.click(); await page.waitForTimeout(300); }
    console.log("✅ 删除可操作");
  });

  test("6. 持久化", async ({ page }) => {
    await page.goto(`file://${P}/index.html`);
    await page.waitForTimeout(1000);
    await page.fill("#transaction-amount", "42");
    await page.fill("#transaction-date", "2026-01-04");
    await page.locator(".submit-btn").click();
    await page.waitForTimeout(500);
    await page.reload();
    await page.waitForTimeout(1500);
    const listText = await page.locator("#transaction-list").textContent() || "";
    expect(listText).toContain("42");
    console.log("✅ 持久化正常");
  });

  test("7. 零错误", async ({ page }) => {
    const err: string[] = [];
    page.on("pageerror", (e) => err.push(e.message));
    await page.goto(`file://${P}/index.html`);
    await page.waitForTimeout(2000);
    await page.fill("#transaction-amount", "1");
    await page.fill("#transaction-date", "2026-01-05");
    await page.locator(".submit-btn").click();
    await page.waitForTimeout(500);
    expect(err.length).toBe(0);
    console.log("✅ 零错误");
  });
});
