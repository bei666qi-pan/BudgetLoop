import { test } from "@playwright/test";

const C = "1e14dc96-4c21-49aa-988c-fde0ecd624d1";

test("验收: 快速检查页面渲染", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));

  await page.goto(`http://localhost:3000/containers/${C}`, {
    waitUntil: "domcontentloaded",
    timeout: 15000,
  });

  // 不等网络空闲，直接取快照
  await page.waitForTimeout(4000);

  // 用 evaluate 取文本（不等 DOM 稳定）
  const bodyText = await page.evaluate(() => document.body.innerText);
  console.log(`=== 页面文本 ===\n${bodyText.substring(0, 600)}\n===`);

  // 按钮数
  const btns = await page.evaluate(() => document.querySelectorAll("button").length);
  console.log(`按钮: ${btns} 个`);

  // 含有 "后端/前端/测试" 的元素
  const sessionEls = await page.evaluate(() => {
    const all = document.querySelectorAll("*");
    const matches: string[] = [];
    for (const el of all) {
      const t = (el as HTMLElement).innerText?.trim();
      if (t && /后端|前端|测试|验收/.test(t) && t.length < 80) {
        matches.push(`<${el.tagName}> "${t.substring(0, 60)}"`);
      }
    }
    return matches.slice(0, 10);
  });
  console.log(`Session元素:\n${sessionEls.join("\n")}`);

  // 错误
  console.log(`\n控制台错误: ${errors.length}`);
  errors.slice(0, 5).forEach((e) => console.log(`  ${e.substring(0, 150)}`));

  // 尝试点击
  const clickable = await page.evaluate(() => {
    const btns = document.querySelectorAll("button");
    for (const b of btns) {
      if (/后端|前端/.test(b.textContent || "")) {
        (b as HTMLElement).click();
        return `已点击: ${b.textContent?.trim().substring(0, 30)}`;
      }
    }
    return "未找到可点击的 Session";
  });
  console.log(`点击结果: ${clickable}`);
  await page.waitForTimeout(1000);

  console.log("\n✅ 诊断完成");
});
