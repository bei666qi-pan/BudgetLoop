import { expect, test } from "@playwright/test";

type GatewayStatus = {
  type: string;
  configured: boolean;
  recommendation_enabled: boolean;
  recommendation_model: string | null;
  default_model: string | null;
  healthy: boolean;
  reason_code: string | null;
  status_class: string | null;
};

type TaskDraft = {
  schema_version: number;
  state: string;
  intent: {
    title: string;
    goal: string;
    acceptance_criteria: string;
    shared_context: string;
  };
  team: {
    preset: { id: string; name: string };
    confidence: number;
    reason: string;
    matched_signals: string[];
  };
  provenance: {
    source: "ai" | "local_fallback";
    runtime: string;
    gateway_type: string;
    model: string | null;
    status_class: string | null;
    fallback_reason: string | null;
    duration_ms: number;
  };
};

const EXPECTED_MODEL = process.env.E2E_MODEL ?? "deepseek-v4-flash";

test.describe("real DeepSeek planning chain", () => {
  test("browser -> Next.js BFF -> FastAPI -> real model -> validated UI", async ({ page, request }) => {
    test.setTimeout(180_000);

    const statusResponse = await request.get("/api/control/api/ai-gateway/status");
    const statusBody = await statusResponse.text();
    expect(statusResponse.status(), statusBody).toBe(200);
    const status = JSON.parse(statusBody) as GatewayStatus;

    expect(status).toMatchObject({
      type: "compatible",
      configured: true,
      recommendation_enabled: true,
      recommendation_model: EXPECTED_MODEL,
      default_model: EXPECTED_MODEL,
      healthy: true,
      reason_code: null,
      status_class: "2xx",
    });

    const publicStatus = JSON.stringify(status);
    expect(publicStatus).not.toMatch(/sk-[A-Za-z0-9_-]{8,}/i);
    expect(publicStatus).not.toContain("api_key");

    await page.goto("/");
    await expect(page.getByRole("heading", { name: "你想完成什么？" })).toBeVisible();

    const marker = `REAL-E2E-${Date.now()}`;
    const goal = `${marker}：分析一个个人预算应用中月度支出突然增加的原因，给出可验证的排查步骤、验收条件和风险边界。`;
    await page.locator("#home-goal").fill(goal);

    const [draftResponse] = await Promise.all([
      page.waitForResponse(
        (response) =>
          response.request().method() === "POST" &&
          response.url().includes("/api/control/api/task-drafts"),
        { timeout: 150_000 },
      ),
      page.getByRole("button", { name: "生成建议配置" }).click(),
    ]);

    const draftBody = await draftResponse.text();
    expect(draftResponse.status(), draftBody).toBe(200);
    const draft = JSON.parse(draftBody) as TaskDraft;

    expect(draft.schema_version).toBe(1);
    expect(draft.state).toBe("ready");
    expect(draft.intent.title.trim().length).toBeGreaterThan(0);
    expect(draft.intent.goal.trim().length).toBeGreaterThan(0);
    expect(draft.intent.acceptance_criteria.trim().length).toBeGreaterThan(0);
    expect(draft.team.preset.id.trim().length).toBeGreaterThan(0);
    expect(draft.team.confidence).toBeGreaterThanOrEqual(1);
    expect(draft.team.confidence).toBeLessThanOrEqual(100);
    expect(draft.team.matched_signals.length).toBeGreaterThan(0);

    expect(draft.provenance).toMatchObject({
      source: "ai",
      runtime: "ai-gateway",
      gateway_type: "compatible",
      model: EXPECTED_MODEL,
      status_class: "2xx",
      fallback_reason: null,
    });
    expect(draft.provenance.duration_ms).toBeGreaterThan(0);

    await expect(page.getByText("建议配置已就绪", { exact: true })).toBeVisible();
    await expect(page.getByText("AI 建议 · 已校验", { exact: true })).toBeVisible();
    await expect(page.getByText("本地建议 · AI 暂不可用", { exact: true })).toHaveCount(0);
    await expect(page.getByRole("heading", { name: "确认这份配置，就可以开始" })).toBeVisible();
  });
});
