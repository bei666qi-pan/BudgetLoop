import { NextRequest } from "next/server";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const ALLOWED_METHODS = new Set(["GET", "POST", "PUT", "PATCH", "DELETE"]);
const MAX_REQUEST_BYTES = 110 * 1024 * 1024;
const REQUEST_HEADERS = ["accept", "content-type", "idempotency-key", "last-event-id"];
const RESPONSE_HEADERS = ["cache-control", "content-disposition", "content-type"];

type RouteContext = { params: Promise<{ path: string[] }> };

function config(): { base: URL; token: string } | null {
  const raw = process.env.CONTROL_PLANE_API_BASE?.trim() || "http://localhost:8000";
  const token = process.env.CONTROL_PLANE_API_TOKEN?.trim() || "";
  try {
    const base = new URL(raw);
    if (!token || !["http:", "https:"].includes(base.protocol) || base.username || base.password) {
      return null;
    }
    return { base, token };
  } catch {
    return null;
  }
}

function boundedBody(request: NextRequest): ReadableStream<Uint8Array> | undefined {
  if (!request.body || request.method === "GET") return undefined;
  let received = 0;
  return request.body.pipeThrough(new TransformStream<Uint8Array, Uint8Array>({
    transform(chunk, controller) {
      received += chunk.byteLength;
      if (received > MAX_REQUEST_BYTES) {
        controller.error(new Error("request_too_large"));
        return;
      }
      controller.enqueue(chunk);
    },
  }));
}

async function proxyControlPlane(request: NextRequest, context: RouteContext) {
  if (!ALLOWED_METHODS.has(request.method)) {
    return Response.json({ detail: "unsupported proxy method" }, { status: 405 });
  }
  const length = Number(request.headers.get("content-length") || "0");
  if (Number.isFinite(length) && length > MAX_REQUEST_BYTES) {
    return Response.json({ detail: "request body is too large" }, { status: 413 });
  }
  const { path } = await context.params;
  if (!path.length || path[0] !== "api" || path.some((part) => !part || part === "." || part === "..")) {
    return Response.json({ detail: "unsupported control-plane path" }, { status: 404 });
  }
  const selected = config();
  if (!selected) {
    return Response.json({ detail: "control plane proxy is not configured" }, { status: 503 });
  }
  const target = new URL(path.map(encodeURIComponent).join("/"), `${selected.base.toString().replace(/\/$/, "")}/`);
  target.search = request.nextUrl.search;
  const headers = new Headers({ Authorization: `Bearer ${selected.token}` });
  for (const name of REQUEST_HEADERS) {
    const value = request.headers.get(name);
    if (value) headers.set(name, value);
  }
  try {
    const body = boundedBody(request);
    const upstream = await fetch(target, {
      method: request.method,
      headers,
      body,
      cache: "no-store",
      redirect: "manual",
      ...(body ? { duplex: "half" } : {}),
    } as RequestInit & { duplex?: "half" });
    const responseHeaders = new Headers();
    for (const name of RESPONSE_HEADERS) {
      const value = upstream.headers.get(name);
      if (value) responseHeaders.set(name, value);
    }
    responseHeaders.set("x-content-type-options", "nosniff");
    return new Response(upstream.body, {
      status: upstream.status,
      statusText: upstream.statusText,
      headers: responseHeaders,
    });
  } catch (error) {
    const tooLarge = error instanceof Error && error.message === "request_too_large";
    return Response.json(
      { detail: tooLarge ? "request body is too large" : "control plane is unavailable" },
      { status: tooLarge ? 413 : 502 },
    );
  }
}

export const GET = proxyControlPlane;
export const POST = proxyControlPlane;
export const PUT = proxyControlPlane;
export const PATCH = proxyControlPlane;
export const DELETE = proxyControlPlane;
