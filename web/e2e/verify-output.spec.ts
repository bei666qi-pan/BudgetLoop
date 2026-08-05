import { test, expect } from "@playwright/test";
import path from "path";

const PROJECT = "/Users/qi/Desktop/测试文件夹";

test.describe("Agent Team 产出验收 — 预算追踪器", () => {

  test("1. 文件存在", async () => {
    const fs = await import("fs");
    for (const f of ["index.html", "app.js", "style.css"]) {
      const exists = fs.existsSync(path.join(PROJECT, f));
      console.log(`${f}: ${exists ? "✅" : "❌"}`);
      expect(exists).toBe(true);
    }
  });

  test("2. 页面可打开 — 标题 + 表单", async ({ page }) => {
    await page.goto(`file://${PROJECT}/index.html`);
    await page.waitForTimeout(1000);

    const text = await page.evaluate(() => document.body.innerText);
    
    expect(text).toContain("预算追踪器");
    expect(text).toContain("添加交易");
    expect(text).toContain("交易记录");
    expect(text).toContain("收入");
    expect(text).toContain("支出");

    await page.screenshot({ path: "test-results/budget-tracker-loaded.png" });
    console.log("✅ 页面加载正常");
  });

  test("3. 添加交易 — 余额更新", async ({ page }) => {
    await page.goto(`file://${PROJECT}/index.html`);
    await page.waitForTimeout(1000);

    // 添加收入
    await page.selectOption("#type", "income");
    await page.fill("#amount", "5000");
    await page.selectOption("#category", "工资");
    await page.fill("#note", "月薪");
    await page.click("button[type='submit']");
    await page.waitForTimeout(500);

    // 验证余额
    let text = await page.evaluate(() => document.body.innerText);
    expect(text).toContain("¥5,000.00");
    console.log("✅ 收入添加成功");

    // 添加支出
    await page.selectOption("#type", "expense");
    await page.fill("#amount", "35.5");
    await page.selectOption("#category", "餐饮");
    await page.fill("#note", "午餐");
    await page.click("button[type='submit']");
    await page.waitForTimeout(500);

    text = await page.evaluate(() => document.body.innerText);
    expect(text).toContain("¥4,964.50");
    console.log("✅ 支出添加成功，余额正确");
  });

  test("4. 删除交易", async ({ page }) => {
    await page.goto(`file://${PROJECT}/index.html`);
    await page.waitForTimeout(1000);

    // 添加一笔
    await page.selectOption("#type", "income");
    await page.fill("#amount", "100");
    await page.selectOption("#category", "奖金");
    await page.click("button[type='submit']");
    await page.waitForTimeout(500);

    const beforeText = await page.evaluate(() => document.body.innerText);
    expect(beforeText).toContain("奖金");

    // 删除
    const delBtns = page.locator(".btn-danger");
    const count = await delBtns.count();
    if (count > 0) {
      await delBtns.first().click();
      await page.waitForTimeout(500);
      // 只在交易列表中检查，排除下拉选项
      const listText = await page.evaluate(() => document.getElementById("txn-list")?.innerText || "");
      expect(listText).not.toContain("奖金");
      console.log("✅ 删除成功");
    }
  });

  test("5. localStorage 持久化", async ({ page }) => {
    await page.goto(`file://${PROJECT}/index.html`);
    await page.waitForTimeout(1000);

    // 初始状态
    let text = await page.evaluate(() => document.body.innerText);
    const hasExisting = text.includes("¥");

    // 添加交易
    await page.selectOption("#type", "expense");
    await page.fill("#amount", "42");
    await page.selectOption("#category", "交通");
    await page.click("button[type='submit']");
    await page.waitForTimeout(500);

    // 刷新
    await page.reload();
    await page.waitForTimeout(1000);

    text = await page.evaluate(() => document.body.innerText);
    expect(text).toContain("交通");
    console.log("✅ 刷新后数据保留");
  });

  test("6. 过滤功能", async ({ page }) => {
    await page.goto(`file://${PROJECT}/index.html`);
    await page.waitForTimeout(1000);

    // 添加收入
    await page.selectOption("#type", "income");
    await page.fill("#amount", "200");
    await page.selectOption("#category", "投资");
    await page.click("button[type='submit']");
    await page.waitForTimeout(300);

    // 添加支出
    await page.selectOption("#type", "expense");
    await page.fill("#amount", "50");
    await page.selectOption("#category", "餐饮");
    await page.click("button[type='submit']");
    await page.waitForTimeout(300);

    // 点"收入"过滤，只在交易列表中检查
    await page.click("button[data-filter='income']");
    await page.waitForTimeout(500);

    let listText = await page.evaluate(() => document.getElementById("txn-list")?.innerText || "");
    expect(listText).toContain("投资");
    expect(listText).not.toContain("餐饮");
    console.log("✅ 收入过滤正常");

    // 点"支出"过滤
    await page.click("button[data-filter='expense']");
    await page.waitForTimeout(500);
    listText = await page.evaluate(() => document.getElementById("txn-list")?.innerText || "");
    expect(listText).not.toContain("投资");
    expect(listText).toContain("餐饮");
    console.log("✅ 支出过滤正常");
  });

  test("7. 无控制台错误", async ({ page }) => {
    const errors: string[] = [];
    page.on("pageerror", (e) => errors.push(e.message));

    await page.goto(`file://${PROJECT}/index.html`);
    await page.waitForTimeout(2000);

    // 交互
    await page.selectOption("#type", "expense");
    await page.fill("#amount", "10");
    await page.selectOption("#category", "购物");
    await page.click("button[type='submit']");
    await page.waitForTimeout(500);

    const delBtns = page.locator(".btn-danger");
    if (await delBtns.count() > 0) {
      await delBtns.first().click();
      await page.waitForTimeout(300);
    }

    await page.click("button[data-filter='income']");
    await page.waitForTimeout(300);
    await page.click("button[data-filter='all']");
    await page.waitForTimeout(300);

    console.log(`控制台错误: ${errors.length}`);
    errors.forEach((e) => console.log(`  ${e.substring(0, 120)}`));
    expect(errors.length).toBe(0);
    console.log("✅ 零错误");
  });
});
