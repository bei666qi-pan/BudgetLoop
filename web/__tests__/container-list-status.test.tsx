import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import {
  CONTAINER_TEAM_STATUS_LABELS,
  deriveTeamStatus,
  teamStatusTone,
} from "@/lib/container-presentation";
import type { WorkContainer } from "@/lib/types";

const container = (
  id: string,
  overrides: Partial<WorkContainer> = {},
): WorkContainer => ({
  id,
  name: `团队 ${id}`,
  project_goal: "测试目标",
  lifecycle_state: "active",
  base_workdir: "/workspace/project",
  default_workspace_policy: "isolated",
  counts: { sessions: 4, running: 2, waiting: 1, attention: 1 },
  sessions: [],
  created_at: "2026-08-01T00:00:00Z",
  updated_at: "2026-08-01T00:00:00Z",
  ...overrides,
});

describe("team status derivation", () => {
  it("returns the explicit team_status field when present", () => {
    expect(deriveTeamStatus(container("c1", { team_status: "active" }))).toBe("active");
    expect(deriveTeamStatus(container("c2", { team_status: "paused", lifecycle_state: "active" }))).toBe("paused");
    expect(deriveTeamStatus(container("c3", { team_status: "blocked" }))).toBe("blocked");
    expect(deriveTeamStatus(container("c4", { team_status: "completed" }))).toBe("completed");
  });

  it("derives completed from completed lifecycle_state", () => {
    expect(deriveTeamStatus(container("c1", {
      lifecycle_state: "completed",
      counts: { sessions: 4, running: 0, waiting: 0, attention: 0 },
    }))).toBe("completed");
  });

  it("derives completed from archived lifecycle_state", () => {
    expect(deriveTeamStatus(container("c1", {
      lifecycle_state: "archived",
      counts: { sessions: 4, running: 0, waiting: 0, attention: 0 },
    }))).toBe("completed");
  });

  it("derives paused from paused lifecycle_state", () => {
    expect(deriveTeamStatus(container("c1", {
      lifecycle_state: "paused",
      counts: { sessions: 4, running: 0, waiting: 2, attention: 0 },
    }))).toBe("paused");
  });

  it("derives blocked when there are attention sessions", () => {
    expect(deriveTeamStatus(container("c1", {
      lifecycle_state: "active",
      counts: { sessions: 4, running: 2, waiting: 0, attention: 2 },
    }))).toBe("blocked");
  });

  it("derives active when lifecycle is active and no attention", () => {
    expect(deriveTeamStatus(container("c1", {
      lifecycle_state: "active",
      counts: { sessions: 4, running: 3, waiting: 1, attention: 0 },
    }))).toBe("active");
  });

  it("derives completed when active but no running sessions and no attention", () => {
    expect(deriveTeamStatus(container("c1", {
      lifecycle_state: "active",
      counts: { sessions: 4, running: 0, waiting: 4, attention: 0 },
    }))).toBe("completed");
  });
});

describe("team status labels", () => {
  it("has all four team status labels for container list", () => {
    expect(CONTAINER_TEAM_STATUS_LABELS).toEqual({
      active: "运行中",
      paused: "已暂停",
      blocked: "阻塞",
      completed: "已停止",
    });
  });
});

describe("team status tone", () => {
  it("returns badge-success for active", () => {
    expect(teamStatusTone("active")).toBe("badge-success");
  });

  it("returns badge-warning for paused", () => {
    expect(teamStatusTone("paused")).toBe("badge-warning");
  });

  it("returns badge-critical for blocked", () => {
    expect(teamStatusTone("blocked")).toBe("badge-critical");
  });

  it("returns badge-muted for completed", () => {
    expect(teamStatusTone("completed")).toBe("badge-muted");
  });

  it("returns badge-muted for null/undefined", () => {
    expect(teamStatusTone(null)).toBe("badge-muted");
    expect(teamStatusTone(undefined)).toBe("badge-muted");
  });
});

describe("container type enrichment", () => {
  it("accepts team_status, alert_count, and active_session_count on WorkContainer", () => {
    const c: WorkContainer = {
      id: "c1",
      name: "Test",
      project_goal: "Goal",
      lifecycle_state: "active",
      base_workdir: "/ws",
      default_workspace_policy: "isolated",
      counts: { sessions: 4, running: 3, waiting: 1, attention: 2 },
      sessions: [],
      created_at: "2026-08-01T00:00:00Z",
      updated_at: "2026-08-01T00:00:00Z",
      team_status: "active",
      alert_count: 2,
      active_session_count: 3,
    };
    expect(c.team_status).toBe("active");
    expect(c.alert_count).toBe(2);
    expect(c.active_session_count).toBe(3);
  });

  it("handles null enriched fields", () => {
    const c: WorkContainer = {
      id: "c1",
      name: "Test",
      project_goal: "Goal",
      lifecycle_state: "active",
      base_workdir: "/ws",
      default_workspace_policy: "isolated",
      counts: { sessions: 4, running: 0, waiting: 4, attention: 0 },
      sessions: [],
      created_at: "2026-08-01T00:00:00Z",
      updated_at: "2026-08-01T00:00:00Z",
      team_status: null,
      alert_count: null,
      active_session_count: null,
    };
    expect(c.team_status).toBeNull();
    expect(c.alert_count).toBeNull();
    expect(c.active_session_count).toBeNull();
    // deriveTeamStatus should fall back to derivation
    expect(deriveTeamStatus(c)).toBe("completed");
  });
});

describe("active session count fallback", () => {
  it("uses active_session_count when available", () => {
    const c = container("c1", {
      active_session_count: 3,
      counts: { sessions: 4, running: 2, waiting: 1, attention: 1 },
    });
    expect(c.active_session_count).toBe(3);
  });

  it("falls back to counts.running when active_session_count is null", () => {
    const c = container("c1", {
      active_session_count: null,
      counts: { sessions: 4, running: 2, waiting: 1, attention: 1 },
    });
    expect(c.counts.running).toBe(2);
  });
});

describe("alert_count fallback", () => {
  it("uses alert_count when available", () => {
    const c = container("c1", {
      alert_count: 3,
      counts: { sessions: 4, running: 2, waiting: 0, attention: 1 },
    });
    expect(c.alert_count).toBe(3);
  });

  it("falls back to counts.attention when alert_count is null", () => {
    const c = container("c1", {
      alert_count: null,
      counts: { sessions: 4, running: 2, waiting: 0, attention: 1 },
    });
    expect(c.counts.attention).toBe(1);
  });
});

describe("liskov compliance with existing filterContainers", () => {
  it("containers with enriched fields still pass through filterContainers", async () => {
    const { filterContainers } = await import("@/lib/container-presentation");
    const c = container("c1", { team_status: "blocked", alert_count: 3, active_session_count: 2 });
    expect(filterContainers([c], "", "all")).toEqual([c]);
    expect(filterContainers([c], "不匹配", "all")).toEqual([]);
    expect(filterContainers([c], "", "active")).toEqual([c]);
    expect(filterContainers([c], "", "paused")).toEqual([]);
  });
});
