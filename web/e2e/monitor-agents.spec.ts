import { test, expect } from "@playwright/test";

const CID = "4ffdaaa6-cc1d-4d32-be71-ac377e5e069a";
const BASE = "http://localhost:3000";

test("监控 Agent 执行 — 等待完成", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));

  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto(`${BASE}/containers/${CID}`, { waitUntil: "domcontentloaded" });
  await page.waitForTimeout(4000);

  let text = await page.evaluate(() => document.body.innerText);
  console.log(`初始状态: ${text.includes("运行中") ? "有运行中" : "暂无运行中"}`);
  
  // 检查 Session 状态
  for (const role of ["前端开发", "后端开发", "测试验收"]) {
    const hasRole = text.includes(role);
    console.log(`  ${role}: ${hasRole ? "存在" : "缺失"}`);
  }

  // 持续监控最多 3 分钟
  let allDone = false;
  for (let i = 0; i < 18; i++) {
    await page.waitForTimeout(10000); // 10s 间隔
    await page.goto(`${BASE}/containers/${CID}`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(3000);
    
    text = await page.evaluate(() => document.body.innerText);
    
    const completed = (text.match(/已完成/g) || []).length;
    const running = (text.match(/运行中/g) || []).length;
    const failed = (text.match(/失败/g) || []).length;
    
    if (completed >= 3) {
      console.log(`✅ 全部完成! (第${i+1}轮, ${Math.round((i+1)*10/60)}分钟)`);
      allDone = true;
      break;
    }
    
    console.log(`第${i+1}轮: 完成=${completed}, 运行=${running}, 失败=${failed}`);
    
    if (failed > 0) {
      console.log(`⚠ 有失败: ${failed} 个`);
    }

    // 检查输出文件
    const resp = await fetch(`${BASE}/api/control/api/work-containers/${CID}`);
    const data = await resp.json();
    for (const s of data.sessions || []) {
      if (s.status === "COMPLETED" || s.status === "FAILED" || s.status === "PARTIAL_COMPLETED") {
        console.log(`  ${s.role}: ${s.status}`);
      }
    }
  }

  if (allDone) {
    await page.screenshot({ path: "test-results/agents-completed.png" });
    console.log("截图已保存");
  }

  console.log(`控制台错误: ${errors.length}`);
  expect(errors.length).toBe(0);

  if (!allDone) {
    console.log("⏰ 3分钟超时，部分未完成");
  }
});
