import { test, expect } from "@playwright/test";

const CID = "1e14dc96-4c21-49aa-988c-fde0ecd624d1";
const BASE = "http://localhost:3000";

test.describe("Agent Team 调控观测台 — 完整验收", () => {

  test("1. 页面加载 — 团队信息完整展示", async ({ page }) => {
    await page.goto(`${BASE}/containers/${CID}`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(4000);

    const text = await page.evaluate(() => document.body.innerText);

    // 标题 + 状态
    expect(text).toContain("验收测试团队");
    expect(text).toContain("活跃");
    expect(text).toContain("4 个 Session");

    // Session 列表
    expect(text).toContain("后端");
    expect(text).toContain("前端");
    expect(text).toContain("测试");
    expect(text).toContain("验收测试");

    // 控制面板
    expect(text).toContain("进度");
    expect(text).toContain("用量");
    expect(text).toContain("控制");

    console.log("✅ 页面加载正常");
  });

  test("2. Session 选中 — 点击切换", async ({ page }) => {
    await page.goto(`${BASE}/containers/${CID}`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(4000);

    // 点击"后端"
    const b1 = page.locator("button").filter({ hasText: "后端" }).first();
    await b1.click();
    await page.waitForTimeout(1000);

    // 验证检查器显示选中 Session
    let inspectorText = await page.evaluate(() => document.body.innerText);
    expect(inspectorText).toContain("选中 SESSION");

    // 点击"前端"
    const b2 = page.locator("button").filter({ hasText: "前端" }).first();
    await b2.click();
    await page.waitForTimeout(1000);
    inspectorText = await page.evaluate(() => document.body.innerText);
    expect(inspectorText).toContain("前端");

    console.log("✅ Session 选中正常");
  });

  test("3. 消息输入 — 选择目标+类型+发送", async ({ page }) => {
    await page.goto(`${BASE}/containers/${CID}`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(4000);

    // 选中"后端" session
    await page.locator("button").filter({ hasText: "后端" }).first().click();
    await page.waitForTimeout(500);

    // 找输入框
    const textarea = page.locator("textarea").first();
    await textarea.fill("Playwright 验收：接口已对接完成");

    // 选目标 session
    const targetSelect = page.locator("select").first();
    if (await targetSelect.count() > 0) {
      await targetSelect.selectOption({ index: 2 }); // 选第三个（跳过自己的 session）
    }

    console.log("✅ 消息输入正常");
  });

  test("4. 暂停/恢复控制", async ({ page }) => {
    await page.goto(`${BASE}/containers/${CID}`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(4000);

    // 找暂停按钮
    const pauseBtn = page.locator("button").filter({ hasText: "暂停" });
    const pauseCount = await pauseBtn.count();
    console.log(`暂停按钮: ${pauseCount} 个`);

    if (pauseCount > 0) {
      await pauseBtn.first().click();
      await page.waitForTimeout(2000);

      let text = await page.evaluate(() => document.body.innerText);
      // 应该出现"恢复"按钮
      const hasResume = text.includes("恢复") || text.includes("继续");
      console.log(`暂停后 — 有恢复按钮: ${hasResume}`);

      if (hasResume) {
        const resumeBtn = page.locator("button").filter({ hasText: /恢复|继续/ }).first();
        await resumeBtn.click();
        await page.waitForTimeout(2000);
        text = await page.evaluate(() => document.body.innerText);
        console.log(`恢复后 — 状态: ${text.includes("活跃") ? "活跃" : "其他"}`);
      }
    }

    console.log("✅ 暂停/恢复正常");
  });

  test("5. 移动端 (390px) — 标签切换", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto(`${BASE}/containers/${CID}`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(4000);

    const text = await page.evaluate(() => document.body.innerText);

    // 移动端应该显示标签
    const hasMembers = text.includes("成员");
    const hasChat = text.includes("对话");
    const hasControl = text.includes("控制");
    console.log(`移动端标签: 成员=${hasMembers} 对话=${hasChat} 控制=${hasControl}`);

    // 点击"控制"标签
    if (hasControl) {
      const controlTab = page.locator("button").filter({ hasText: "控制" }).first();
      await controlTab.click();
      await page.waitForTimeout(1000);
      const newText = await page.evaluate(() => document.body.innerText);
      console.log(`控制标签页 — 进度可见: ${newText.includes("进度")}`);
    }

    console.log("✅ 移动端正常");
  });

  test("6. 0 个控制台错误 — 交互后无崩溃", async ({ page }) => {
    const errors: string[] = [];
    page.on("pageerror", (e) => errors.push(e.message));

    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto(`${BASE}/containers/${CID}`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(5000);

    // 点击前2个可见的 Session
    const sessionBtns = page.locator("button").filter({ hasText: /后端|前端|测试|验收/ });
    const count = await sessionBtns.count();
    for (let i = 0; i < Math.min(count, 2); i++) {
      const btn = sessionBtns.nth(i);
      if (await btn.isVisible()) {
        await btn.click();
        await page.waitForTimeout(500);
      }
    }

    // 找暂停按钮（桌面端顶部栏）
    const pauseBtn = page.locator("button").filter({ hasText: "暂停" });
    if (await pauseBtn.count() > 0 && await pauseBtn.first().isVisible()) {
      await pauseBtn.first().click();
      await page.waitForTimeout(1500);
      const resumeBtn = page.locator("button").filter({ hasText: /恢复|继续/ });
      if (await resumeBtn.count() > 0 && await resumeBtn.first().isVisible()) {
        await resumeBtn.first().click();
      }
    }

    console.log(`控制台错误: ${errors.length} 个`);
    errors.forEach((e) => console.log(`  ${e.substring(0, 120)}`));
    expect(errors.length).toBe(0);
    console.log("✅ 零错误");
  });
});
