/**
 * 诊断测试 — 验证 Session 选中、消息发送、控制功能
 */
import { test } from "@playwright/test";

const CONTAINER_ID = "1e14dc96-4c21-49aa-988c-fde0ecd624d1";

test("诊断: 页面元素分析", async ({ page }) => {
  // 收集浏览器控制台错误
  const errors: string[] = [];
  page.on("console", (msg) => {
    if (msg.type() === "error") errors.push(msg.text());
  });

  await page.goto(`http://localhost:3000/containers/${CONTAINER_ID}`);
  // 不能用 networkidle — 页面有 SSE/轮询持续请求
  await page.waitForLoadState("domcontentloaded");
  await page.waitForTimeout(5000);

  await page.screenshot({ path: "test-results/diag-1-full.png", fullPage: true });

  // 获取页面全部文本
  const allText = await page.textContent("body");
  console.log("=== 页面文本 (前800字) ===");
  console.log(allText?.substring(0, 800));

  console.log("\n=== 控制台错误 ===");
  errors.forEach((e) => console.log(e));

  // 找所有可交互元素
  console.log("\n=== 按钮 ===");
  const buttons = page.locator("button");
  const btnCount = await buttons.count();
  console.log(`按钮总数: ${btnCount}`);
  for (let i = 0; i < Math.min(btnCount, 15); i++) {
    const btn = buttons.nth(i);
    const text = await btn.textContent();
    const cls = await btn.getAttribute("class");
    console.log(`  [${i}] "${text?.trim().substring(0, 30)}" class="${cls?.substring(0, 60)}"`);
  }

  console.log("\n=== 链接/可点击元素 ===");
  const links = page.locator("a, [role='button'], [tabindex]");
  const linkCount = await links.count();
  console.log(`总数: ${linkCount}`);
  for (let i = 0; i < Math.min(linkCount, 15); i++) {
    const el = links.nth(i);
    const text = await el.textContent();
    const role = await el.getAttribute("role");
    console.log(`  [${i}] role="${role}" text="${text?.trim().substring(0, 40)}"`);
  }

  // 找包含 "后端" 或 "前端" 文本的元素
  console.log("\n=== 包含Session角色文本 ===");
  const sessionEls = page.locator("text=/后端|前端|测试|验收/");
  const sessionCount = await sessionEls.count();
  console.log(`找到 ${sessionCount} 个元素`);
  for (let i = 0; i < Math.min(sessionCount, 10); i++) {
    const el = sessionEls.nth(i);
    const tag = await el.evaluate((e) => e.tagName);
    const text = await el.textContent();
    const parent = await el.evaluate((e) => e.parentElement?.tagName);
    console.log(`  [${i}] <${tag}> (parent: <${parent}>): "${text?.trim().substring(0, 60)}"`);
  }

  console.log("\n=== 诊断完成 ===");
});
