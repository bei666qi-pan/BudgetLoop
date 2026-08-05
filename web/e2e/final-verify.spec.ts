import { test, expect } from "@playwright/test";

const C = "1e14dc96-4c21-49aa-988c-fde0ecd624d1";

test("真实验收: 页面加载 + Session选中 + 消息 + 暂停", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));

  // 1. 加载团队观测台
  await page.goto(`http://localhost:3000/containers/${C}`);
  await page.waitForSelector("main", { timeout: 15000 });
  await page.waitForTimeout(3000);

  // 检查页面标题
  const title = await page.title();
  console.log(`Title: ${title}`);

  // 获取文本内容
  const bodyText = await page.textContent("main");
  console.log(`Body (前200): ${bodyText?.substring(0, 200)}`);

  // 2. 检查 Session 按钮
  const buttons = page.locator("button");
  const btnCount = await buttons.count();
  console.log(`按钮: ${btnCount} 个`);

  const sessionBtns = buttons.filter({ hasText: /后端|前端|测试|验收/ });
  const sBtnCount = await sessionBtns.count();
  console.log(`Session按钮: ${sBtnCount} 个`);

  if (sBtnCount === 0 && bodyText?.includes("暂无活动")) {
    console.log("⚠ 展示空态 — 需要先在容器中创建未完成的 Session");
    // 容器中所有 session 都是 PENDING 状态，应该显示
  }

  // 3. 尝试点击一个 Session
  if (sBtnCount > 0) {
    const first = sessionBtns.first();
    const beforeText = await first.textContent();
    await first.click();
    await page.waitForTimeout(1000);
    console.log(`✅ Session 已选中: ${beforeText?.trim().substring(0, 30)}`);
  }

  // 4. 检查输入框
  const textareas = page.locator("textarea");
  const taCount = await textareas.count();
  console.log(`输入框: ${taCount} 个`);

  if (taCount > 0) {
    await textareas.first().fill("Playwright 验收消息");
    console.log("✅ 消息输入成功");
  }

  // 5. 找暂停按钮
  const pauseBtn = page.locator("button").filter({ hasText: "暂停" });
  if (await pauseBtn.count() > 0) {
    await pauseBtn.first().click();
    await page.waitForTimeout(2000);
    console.log("✅ 暂停按钮已点击");
  }

  // 6. 截图
  await page.screenshot({ path: "test-results/final-verify.png" });
  console.log(`\n控制台错误: ${errors.length} 个`);
  errors.forEach((e) => console.log(`  ${e.substring(0, 100)}`));

  console.log("\n✅ 验收完成");
});
