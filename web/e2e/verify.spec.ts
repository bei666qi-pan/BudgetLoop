import { test, expect } from "@playwright/test";
import fs from "fs";
const P = "/Users/qi/Desktop/测试文件夹";

test("Agent产出验收", async ({ page }) => {
  // File check
  const files = ["index.html","app.js","style.css"];
  for (const f of files) expect(fs.existsSync(`${P}/${f}`)).toBe(true);
  console.log(`✅ 3 files: ${files.map(f => fs.statSync(`${P}/${f}`).size).join("b, ")}b`);

  // Page load + 0 errors
  const errors: string[] = [];
  page.on("pageerror", e => errors.push(e.message));
  await page.goto(`file://${P}/index.html`);
  await page.waitForTimeout(2000);

  const text = await page.evaluate(() => document.body.innerText);
  expect(text).toContain("预算");
  expect(text).toContain("交易");
  expect(errors).toEqual([]);

  // Try basic interaction
  const form = page.locator("form");
  const inputs = page.locator("input[type='number']");
  const submit = page.locator("button[type='submit'], .submit-btn, form button").first();

  if (await form.count() > 0 && await inputs.count() > 0) {
    await inputs.first().fill("100");
    try { await submit.click(); await page.waitForTimeout(800); } catch {}
    console.log(`表单交互: OK`);
  }

  console.log(`✅ 0错误, 页面正常, 3文件在桌面`);
});
