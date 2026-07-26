import { NextRequest } from "next/server";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { GET, POST } from "@/app/api/control/[...path]/route";

const context = (path: string[]) => ({ params: Promise.resolve({ path }) });

describe("same-origin control-plane proxy", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    global.fetch = vi.fn();
    process.env.CONTROL_PLANE_API_BASE = "http://control-plane:8000";
    process.env.CONTROL_PLANE_API_TOKEN = "server-only-token";
  });

  afterEach(() => {
    delete process.env.CONTROL_PLANE_API_BASE;
    delete process.env.CONTROL_PLANE_API_TOKEN;
  });

  it("injects server authorization and does not forward browser authorization", async () => {
    global.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ tasks: [] }), {
        status: 200,
        headers: { "content-type": "application/json" },
      }),
    );
    const response = await GET(
      new NextRequest("http://localhost/api/control/api/tasks?limit=2", {
        headers: { Authorization: "Bearer browser-token" },
      }),
      context(["api", "tasks"]),
    );
    expect(response.status).toBe(200);
    const [target, init] = vi.mocked(global.fetch).mock.calls[0];
    expect(String(target)).toBe("http://control-plane:8000/api/tasks?limit=2");
    expect(new Headers(init?.headers).get("authorization")).toBe("Bearer server-only-token");
    expect(await response.json()).toEqual({ tasks: [] });
  });

  it("rejects non-api paths and declared oversized requests", async () => {
    const invalid = await GET(
      new NextRequest("http://localhost/api/control/internal"),
      context(["internal"]),
    );
    expect(invalid.status).toBe(404);

    const oversized = await POST(
      new NextRequest("http://localhost/api/control/api/project-uploads", {
        method: "POST",
        headers: { "content-length": String(111 * 1024 * 1024) },
        body: "x",
      }),
      context(["api", "project-uploads"]),
    );
    expect(oversized.status).toBe(413);
    expect(global.fetch).not.toHaveBeenCalled();
  });

  it("fails closed when the server token is absent", async () => {
    delete process.env.CONTROL_PLANE_API_TOKEN;
    const response = await GET(
      new NextRequest("http://localhost/api/control/api/health"),
      context(["api", "health"]),
    );
    expect(response.status).toBe(503);
  });
});
