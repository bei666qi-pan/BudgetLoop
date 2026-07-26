import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import NewTaskPage from "@/app/new/page";

const push = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ push }) }));

beforeEach(() => {
  push.mockReset();
  delete window.webkit;
});

describe("advanced task folder picker", () => {
  it("keeps the native picker beside the field and applies the returned folder", async () => {
    const user = userEvent.setup();
    const postMessage = vi.fn();
    window.webkit = { messageHandlers: { budgetloopPickProjectDir: { postMessage } } };
    render(<NewTaskPage />);

    const field = screen.getByLabelText("项目文件夹 （可选，仅完全访问模式使用）");
    const button = screen.getByRole("button", { name: "选择文件夹" });
    expect(button.parentElement).toContainElement(field);

    await user.click(button);
    expect(postMessage).toHaveBeenCalledWith(null);

    act(() => window.budgetloopSetProjectDir?.("/tmp/budgetloop-project"));
    expect(field).toHaveValue("/tmp/budgetloop-project");
    expect(screen.getByRole("radio", { name: /完全访问模式/ })).toBeChecked();
  });

  it("keeps the path read-only and explains when the native bridge is unavailable", async () => {
    const user = userEvent.setup();
    render(<NewTaskPage />);
    const field = screen.getByLabelText("项目文件夹 （可选，仅完全访问模式使用）");
    expect(field).toHaveAttribute("readonly");
    await user.click(screen.getByRole("button", { name: "选择文件夹" }));
    expect(screen.getByText("请在 BudgetLoop macOS App 中选择项目文件夹。")).toBeInTheDocument();
  });
});
