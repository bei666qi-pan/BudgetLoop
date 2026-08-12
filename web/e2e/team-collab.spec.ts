import { test, expect } from "@playwright/test";
import fs from "fs";
import path from "path";

const BASE = "http://localhost:3000";
const DESKTOP = "/Users/qi/Desktop/测试文件夹";

test("Agent Team 实时协作验收", async ({ page }) => {
  // Step 1: Open container list, find active container
  await page.goto(`${BASE}/containers`, { waitUntil: "domcontentloaded" });
  await page.waitForTimeout(3000);

  // Find and click the collaboration team container
  const rows = page.locator("a[href*='/containers/']");
  const count = await rows.count();
  let found = false;
  for (let i = 0; i < count; i++) {
    const href = await rows.nth(i).getAttribute("href");
    const text = await rows.nth(i).textContent();
    if (href && href.includes("/containers/") && !href.includes("/new") && text && text.length > 10) {
      console.log(`进入: ${text.substring(0, 40)}`);
      await rows.nth(i).click();
      found = true;
      break;
    }
  }
  if (!found) {
    console.log("No active containers found");
    return;
  }

  await page.waitForTimeout(4000);

  // Step 2: Check team observatory renders
  let bodyText = await page.evaluate(() => document.body.innerText);
  console.log(`页面标题: ${bodyText.includes("协作") ? "YES" : "NO"}`);
  console.log(`Session列表: ${bodyText.includes("前端") || bodyText.includes("后端") ? "YES" : "NO"}`);

  // Take initial screenshot
  await page.screenshot({ path: "test-results/collab-1-initial.png" });

  // Step 3: Monitor for 2 minutes, checking files every 15s
  for (let i = 0; i < 8; i++) {
    await page.waitForTimeout(15000);

    // Refresh page to get latest state
    bodyText = await page.evaluate(() => document.body.innerText);

    const running = (bodyText.match(/运行中/g) || []).length;
    const completed = (bodyText.match(/已完成/g) || []).length;
    const failed = (bodyText.match(/失败/g) || []).length;

    // Check desktop files
    let desktopFiles: string[] = [];
    try {
      desktopFiles = fs.readdirSync(DESKTOP).filter(f =>
        f.endsWith('.html') || f.endsWith('.js') || f.endsWith('.css')
      );
    } catch {}

    console.log(`[${i+1}] 运行:${running} 完成:${completed} 失败:${failed} | 文件:${desktopFiles.join(",") || "无"}`);

    if (desktopFiles.length >= 3) {
      console.log("✅ 全部3个文件已生成！");
      await page.screenshot({ path: "test-results/collab-2-complete.png" });
      break;
    }

    if (failed >= 2 && desktopFiles.length > 0) {
      console.log("⚠ Agents失败但有产出文件");
      break;
    }
  }

  // Step 4: Final verification
  let finalFiles: string[] = [];
  try {
    finalFiles = fs.readdirSync(DESKTOP).filter(f =>
      f.endsWith('.html') || f.endsWith('.js') || f.endsWith('.css')
    );
  } catch {}

  console.log(`\n最终桌面文件: ${finalFiles.join(", ") || "无"}`);
  await page.screenshot({ path: "test-results/collab-3-final.png" });

  // Verify at least one file was created by agents
  expect(finalFiles.length).toBeGreaterThan(0);
});
