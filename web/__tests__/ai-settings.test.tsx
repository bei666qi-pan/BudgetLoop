import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import AISettingsPage from "@/app/settings/ai/page";
import { apiFetch } from "@/lib/api";

vi.mock("@/lib/api", () => ({ apiFetch: vi.fn() }));

const apiFetchMock = vi.mocked(apiFetch);
const saved = {
  kind: "compatible",
  base_url: "https://gateway.example/v1",
  console_url: "",
  recommendation_model: "recommend-model",
  default_model: "app-model",
  deployment_label: "企业内部模型",
  network_label: "企业安全接入",
  reasoning_effort: "max",
  thinking_enabled: true,
  thinking_budget_tokens: 65536,
  managed_app_inheritance_enabled: true,
  secret_configured: true,
  secret_store: "macos_keychain",
};
const status = {
  type: "compatible",
  configured: true,
  healthy: false,
  recommendation_enabled: true,
  recommendation_model: "recommend-model",
  default_model: "app-model",
  deployment_label: "企业内部模型",
  network_label: "企业安全接入",
  reasoning_effort: "max",
  thinking_enabled: true,
  thinking_budget_tokens: 65536,
  managed_app_runtime: { enabled: true },
  console_url: null,
  protocols: ["OpenAI-compatible"],
  routing: "由自定义兼容网关负责",
  semantic_ai_router: false,
  provenance: null,
  reason_code: "gateway_unreachable",
  status_class: null,
};

describe("AI settings", () => {
  beforeEach(() => {
    apiFetchMock.mockReset();
    apiFetchMock.mockImplementation(async (path, init) => {
      if (path.endsWith("/settings") && init?.method === "PUT") return saved as never;
      if (path.endsWith("/settings")) return saved as never;
      return status as never;
    });
  });

  it("loads personalized settings without rendering the saved secret", async () => {
    render(<AISettingsPage />);
    expect(await screen.findByDisplayValue("企业内部模型")).toBeInTheDocument();
    expect(screen.getByText(/密钥已配置，页面不会读取或回显/)).toBeInTheDocument();
    expect(screen.getByLabelText("API Key")).toHaveValue("");
    expect(screen.getByRole("checkbox", { name: /AI 应用自动继承/ })).toBeChecked();
    expect(screen.getByText("尚未连通")).toBeInTheDocument();
    expect(screen.getByText(/企业安全接入：无法到达安全网关/)).toBeInTheDocument();
  });

  it("can disable default inheritance and sends a replacement key only on save", async () => {
    const user = userEvent.setup();
    render(<AISettingsPage />);
    await screen.findByDisplayValue("企业内部模型");
    await user.click(screen.getByRole("checkbox", { name: /AI 应用自动继承/ }));
    await user.type(screen.getByLabelText("API Key"), "replacement-secret");
    await user.click(screen.getByRole("button", { name: /安全保存并检查连接/ }));
    await waitFor(() => {
      const put = apiFetchMock.mock.calls.find((call) => call[1]?.method === "PUT");
      expect(put).toBeTruthy();
      const body = JSON.parse(String(put?.[1]?.body));
      expect(body.managed_app_inheritance_enabled).toBe(false);
      expect(body.api_key).toBe("replacement-secret");
    });
  });
});
