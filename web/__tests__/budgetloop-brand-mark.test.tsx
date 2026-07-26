import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import AppShell from "@/components/AppShell";
import { BudgetLoopBrandMark } from "@/components/brand/BudgetLoopBrandMark";

vi.mock("next/navigation", () => ({ usePathname: () => "/" }));
vi.mock("@/lib/api", () => ({ checkHealth: vi.fn().mockResolvedValue(true) }));

describe("BudgetLoop brand mark", () => {
  it("renders the static interlocking-loop geometry", () => {
    const { container } = render(<BudgetLoopBrandMark className="h-9 w-9" />);
    expect(container.querySelector('[data-brand-mark="budgetloop"]')).toBeInTheDocument();
    expect(container.querySelectorAll("path")).toHaveLength(2);
    expect(container.querySelector("filter")).not.toBeInTheDocument();
  });

  it("places the mark in the persistent, named product link", () => {
    const { container } = render(<AppShell><p>Workspace</p></AppShell>);
    expect(screen.getByRole("link", { name: "BudgetLoop 首页" })).toContainElement(
      container.querySelector('[data-brand-mark="budgetloop"]'),
    );
  });

  it("ships an equivalent branded SVG metadata icon", () => {
    const icon = readFileSync(resolve(process.cwd(), "app/icon.svg"), "utf8");
    expect(icon).toContain('aria-label="BudgetLoop"');
    expect((icon.match(/<path /g) ?? [])).toHaveLength(2);
    expect(icon).toContain("#2668E8");
  });
});
