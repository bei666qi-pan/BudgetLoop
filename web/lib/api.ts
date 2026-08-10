// 浏览器统一走同源 Next.js BFF；生产凭证只由服务端 route handler 注入。

export const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE ?? "/api/control";

export class ApiError extends Error {
  status: number | null;

  constructor(message: string, status: number | null = null) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }

  /** 网络层失败（API 不可达）时 status 为 null */
  get isUnreachable(): boolean {
    return this.status === null;
  }
}

async function parseErrorMessage(res: Response): Promise<string> {
  try {
    const text = await res.text();
    if (!text) return `HTTP ${res.status}`;
    try {
      const data = JSON.parse(text) as { detail?: unknown; message?: unknown };
      if (typeof data.detail === "string") return data.detail;
      if (typeof data.message === "string") return data.message;
      return `HTTP ${res.status}: ${text.slice(0, 200)}`;
    } catch {
      return `HTTP ${res.status}: ${text.slice(0, 200)}`;
    }
  } catch {
    return `HTTP ${res.status}`;
  }
}

export async function apiFetch<T>(
  path: string,
  init: RequestInit = {},
): Promise<T> {
  let res: Response;
  try {
    const headers = new Headers(init.headers);
    if (!(init.body instanceof FormData) && !headers.has("Content-Type")) {
      headers.set("Content-Type", "application/json");
    }
    res = await fetch(`${API_BASE}${path}`, {
      ...init,
      cache: "no-store",
      headers,
    });
  } catch (err) {
    throw new ApiError(
      `无法连接 API（${API_BASE}）：${err instanceof Error ? err.message : String(err)}`,
      null,
    );
  }
  if (!res.ok) {
    throw new ApiError(await parseErrorMessage(res), res.status);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export async function checkHealth(): Promise<boolean> {
  try {
    const res = await fetch(`${API_BASE}/api/health`, { cache: "no-store" });
    return res.ok;
  } catch {
    return false;
  }
}

/** 通过同源服务端代理下载导出文件。 */
export const fetchApi = apiFetch;

export async function downloadFile(path: string, filename: string): Promise<void> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}`, {
      cache: "no-store",
    });
  } catch (err) {
    throw new ApiError(
      `无法连接 API（${API_BASE}）：${err instanceof Error ? err.message : String(err)}`,
      null,
    );
  }
  if (!res.ok) {
    throw new ApiError(await parseErrorMessage(res), res.status);
  }
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

export async function uploadProjectFolder<T>(files: File[]): Promise<T> {
  const body = new FormData();
  for (const file of files) {
    body.append("files", file, file.name);
    body.append("paths", file.webkitRelativePath || file.name);
  }
  return apiFetch<T>("/api/project-uploads", { method: "POST", body });
}

/** 生成幂等键（新建任务重复提交保护）。 */
export function idempotencyKey(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  return `${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

// ---- Team Inspector API ----

import type {
  TeamInspectorProgress,
  TeamInspectorUsage,
  TeamBudgetPatch,
  TeamBudgetPatchResponse,
  SessionBudgetPatch,
  JudgeState,
  TeamChatMessage,
} from "./types";

export async function fetchJudgeState(containerId: string): Promise<JudgeState> {
  return apiFetch<JudgeState>(`/api/work-containers/${containerId}/judge`);
}

export async function resumeJudge(
  containerId: string,
  evidence: Record<string, unknown> = {},
): Promise<JudgeState> {
  return apiFetch<JudgeState>(`/api/work-containers/${containerId}/judge/resume`, {
    method: "POST",
    headers: { "Idempotency-Key": idempotencyKey() },
    body: JSON.stringify({ evidence }),
  });
}

export async function fetchTeamMessages(containerId: string): Promise<TeamChatMessage[]> {
  const result = await apiFetch<{ messages: TeamChatMessage[] }>(
    `/api/work-containers/${containerId}/messages?limit=500`,
  );
  return result.messages;
}

/** 获取团队进度聚合。 */
export async function fetchTeamProgress(
  containerId: string,
): Promise<TeamInspectorProgress> {
  return apiFetch<TeamInspectorProgress>(
    `/api/work-containers/${containerId}/progress`,
    { method: "GET" },
  );
}

/** 获取团队用量详情。 */
export async function fetchTeamUsage(
  containerId: string,
): Promise<TeamInspectorUsage> {
  return apiFetch<TeamInspectorUsage>(
    `/api/work-containers/${containerId}/usage`,
    { method: "GET" },
  );
}

/** 暂停容器（幂等）。 */
export async function pauseContainer(containerId: string): Promise<void> {
  await apiFetch(`/api/work-containers/${containerId}/pause`, {
    method: "POST",
  });
}

/** 恢复容器（幂等）。 */
export async function resumeContainer(containerId: string): Promise<void> {
  await apiFetch(`/api/work-containers/${containerId}/resume`, {
    method: "POST",
  });
}

/** 停止容器（不可逆，需确认）。 */
export async function stopContainer(containerId: string): Promise<void> {
  await apiFetch(`/api/work-containers/${containerId}/stop`, {
    method: "POST",
  });
}

/** 调整团队预算。 */
export async function patchContainerBudget(
  containerId: string,
  body: TeamBudgetPatch,
): Promise<TeamBudgetPatchResponse> {
  return apiFetch<TeamBudgetPatchResponse>(
    `/api/work-containers/${containerId}/budget`,
    { method: "PATCH", body: JSON.stringify(body) },
  );
}

/** 暂停指定 Session（幂等）。 */
export async function pauseSession(
  containerId: string,
  sessionId: string,
): Promise<void> {
  await apiFetch(
    `/api/work-containers/${containerId}/sessions/${sessionId}/pause`,
    { method: "PATCH" },
  );
}

/** 恢复指定 Session（幂等）。 */
export async function resumeSession(
  containerId: string,
  sessionId: string,
): Promise<void> {
  await apiFetch(
    `/api/work-containers/${containerId}/sessions/${sessionId}/resume`,
    { method: "PATCH" },
  );
}

/** 取消指定 Session（不可逆）。 */
export async function cancelSession(
  containerId: string,
  sessionId: string,
): Promise<void> {
  await apiFetch(
    `/api/work-containers/${containerId}/sessions/${sessionId}/cancel`,
    { method: "POST" },
  );
}

/** 调整 Session 预算。 */
export async function patchSessionBudget(
  containerId: string,
  sessionId: string,
  body: SessionBudgetPatch,
): Promise<TeamBudgetPatchResponse> {
  return apiFetch<TeamBudgetPatchResponse>(
    `/api/work-containers/${containerId}/sessions/${sessionId}/budget`,
    { method: "PATCH", body: JSON.stringify(body) },
  );
}

/** 追加纠偏指令到 Session。 */
export async function appendSessionInstruction(
  containerId: string,
  sessionId: string,
  instruction: string,
): Promise<void> {
  await apiFetch(
    `/api/work-containers/${containerId}/sessions/${sessionId}/correct`,
    { method: "POST", body: JSON.stringify({ instruction }) },
  );
}
