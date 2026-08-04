import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import NewTaskPage from "@/app/new/page";

const push = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ push }) }));

beforeEach(() => {
  push.mockReset();
});

describe("advanced task folder picker", () => {
  it("allows manual entry of the project folder path", async () => {
    const user = userEvent.setup();
    render(<NewTaskPage />);

    const field = screen.getByLabelText("项目文件夹 （可选，仅完全访问模式使用）");
    expect(field).not.toHaveAttribute("readonly");
    expect(field).toHaveAttribute("placeholder", "例如：/Users/you/my-project");

    await user.clear(field);
    await user.type(field, "/tmp/budgetloop-project");
    expect(field).toHaveValue("/tmp/budgetloop-project");
  });

  it("no longer has a native folder picker button", () => {
    render(<NewTaskPage />);
    expect(screen.queryByRole("button", { name: "选择文件夹" })).toBeNull();
  });

  it("no longer shows native bridge error", async () => {
    const user = userEvent.setup();
    render(<NewTaskPage />);
    const field = screen.getByLabelText("项目文件夹 （可选，仅完全访问模式使用）");
    expect(field).not.toHaveAttribute("readonly");
    await user.clear(field);
    await user.type(field, "/Users/qi/project");
    expect(field).toHaveValue("/Users/qi/project");
  });
});
