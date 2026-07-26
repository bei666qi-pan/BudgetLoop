import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { BudgetLoopActivityMark } from "@/components/brand/BudgetLoopActivityMark";

describe("BudgetLoopActivityMark", () => {
  it("renders the branded double-loop disturbance with one accessible status", () => {
    const { container } = render(<BudgetLoopActivityMark label="正在分析目标" />);
    expect(screen.getByRole("status", { name: "正在分析目标" })).toHaveAttribute(
      "data-variant",
      "full",
    );
    expect(container.querySelectorAll(".budgetloop-loop")).toHaveLength(2);
    expect(container.querySelector("feTurbulence")).toBeInTheDocument();
    expect(container.querySelector("feDisplacementMap")).toBeInTheDocument();
  });

  it("keeps the compact button label visible without adding another live region", () => {
    const { container } = render(<BudgetLoopActivityMark compact label="正在创建…" />);
    expect(screen.getAllByRole("status")).toHaveLength(1);
    expect(screen.getByRole("status", { name: "正在创建…" })).toHaveAttribute(
      "data-variant",
      "compact",
    );
    expect(container).toHaveTextContent("正在创建…");
  });
});
