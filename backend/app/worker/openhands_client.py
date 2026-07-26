"""OpenHands agent-server 同步客户端（httpx）。

以 https://docs.openhands.dev/openapi/agent-sdk.json 核实为准：
- POST /api/conversations          StartConversationRequest -> ConversationInfo
- POST /api/conversations/{id}/events   SendMessageRequest(role, content, run) -> Success
- POST /api/conversations/{id}/run      后台启动运行 -> Success（409 = 已在运行）
- POST /api/conversations/{id}/pause    -> Success
- GET  /api/conversations/{id}          -> ConversationInfo（execution_status / stats）
- GET  /api/conversations/{id}/events/search?page_id&limit&kind&sort_order -> EventPage
- POST /api/bash/execute_bash_command   ExecuteBashRequest(command, cwd?, timeout=300) -> BashOutput
- GET  /api/git/diff/{path}             -> GitDiff(modified, original)
- POST /api/file/upload/{path}          multipart file -> Success

鉴权头：X-Session-API-Key。
重试：429 / 5xx / 传输错误指数退避，最多 3 次。

注意（spec 核实结论）：没有 per-run 迭代上限参数，max_iterations 是
conversation 级配置（StartConversationRequest.max_iterations，min 1，默认 500）。
因此"一个 BudgetLoop iteration 只驱动一个 OpenHands step"无法通过
per-run 参数实现，由 orchestrator 用等待 idle 的方式近似（见 orchestrator）。
"""
from __future__ import annotations

import time
import uuid

import httpx

# execution_status 终态/可等待态（ConversationExecutionStatus 枚举）
IDLE_STATUSES = frozenset({"idle", "finished", "paused", "error", "stuck", "waiting_for_confirmation"})
AMBIGUOUS_PRE_START_STATUSES = frozenset({"idle", "finished"})

EVENTS_PAGE_LIMIT = 100  # spec: limit <= 100
DEFAULT_CODING_TOOLS = (
    {"name": "terminal", "params": {}},
    {"name": "file_editor", "params": {}},
    {"name": "task_tracker", "params": {}},
)


class AgentServerError(Exception):
    """agent-server 调用失败（重试耗尽 / 4xx / 超时等待）。"""


class AgentServerClient:
    def __init__(
        self,
        base_url: str,
        session_key: str,
        *,
        timeout: float = 60.0,
        max_retries: int = 3,
        backoff_base: float = 0.5,
    ):
        self.base_url = base_url.rstrip("/")
        self.max_retries = max_retries
        self.backoff_base = backoff_base
        self.conversation_id: uuid.UUID | None = None
        self._client = httpx.Client(
            base_url=self.base_url,
            headers={"X-Session-API-Key": session_key},
            timeout=timeout,
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "AgentServerClient":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    # ------------------------------------------------------------------
    # 基础请求：重试 + 错误封装
    # ------------------------------------------------------------------
    def _request(
        self,
        method: str,
        path: str,
        *,
        accepted_statuses: frozenset[int] = frozenset(),
        **kwargs,
    ) -> httpx.Response:
        last_exc: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
                resp = self._client.request(method, path, **kwargs)
            except httpx.TransportError as exc:
                last_exc = exc
                self._backoff(attempt)
                continue
            if resp.status_code in (429,) or resp.status_code >= 500:
                last_exc = AgentServerError(f"{method} {path} -> {resp.status_code}: {resp.text[:500]}")
                self._backoff(attempt)
                continue
            if resp.status_code in accepted_statuses:
                return resp
            if resp.status_code >= 400:
                raise AgentServerError(f"{method} {path} -> {resp.status_code}: {resp.text[:500]}")
            return resp
        raise AgentServerError(f"{method} {path} failed after {self.max_retries + 1} attempts: {last_exc}")

    def _backoff(self, attempt: int) -> None:
        if attempt < self.max_retries:
            time.sleep(self.backoff_base * (2 ** attempt))

    def _conversation_path(self, conversation_id: uuid.UUID | str | None = None) -> str:
        cid = conversation_id or self.conversation_id
        if cid is None:
            raise AgentServerError("conversation_id not set; call create_conversation first")
        return f"/api/conversations/{cid}"

    # ------------------------------------------------------------------
    # Conversation 生命周期
    # ------------------------------------------------------------------
    def create_conversation(
        self,
        *,
        model: str,
        llm_base_url: str,
        llm_api_key: str,
        working_dir: str,
        initial_message: str | None = None,
        conversation_id: uuid.UUID | None = None,
        max_iterations: int = 500,
        usage_id: str = "agent",
        extra_llm: dict | None = None,
    ) -> dict:
        """创建 conversation，返回 ConversationInfo。"""
        llm: dict = {
            "model": model,
            "base_url": llm_base_url,
            "api_key": llm_api_key,
            "usage_id": usage_id,
        }
        if extra_llm:
            llm.update(extra_llm)
        body: dict = {
            "agent": {
                "kind": "Agent",
                "llm": llm,
                "tools": [dict(tool) for tool in DEFAULT_CODING_TOOLS],
            },
            "workspace": {"kind": "LocalWorkspace", "working_dir": working_dir},
            "max_iterations": max_iterations,
        }
        if conversation_id is not None:
            body["conversation_id"] = str(conversation_id)
        if initial_message:
            body["initial_message"] = {
                "role": "user",
                "content": [{"type": "text", "text": initial_message}],
                "run": False,
            }
        info = self._request("POST", "/api/conversations", json=body).json()
        self.conversation_id = uuid.UUID(info["id"])
        return info

    def send_message(self, text: str, *, run: bool = True, conversation_id=None) -> dict:
        body = {
            "role": "user",
            "content": [{"type": "text", "text": text}],
            "run": run,
        }
        return self._request("POST", f"{self._conversation_path(conversation_id)}/events", json=body).json()

    def run_conversation(self, conversation_id=None) -> dict:
        return self._request(
            "POST",
            f"{self._conversation_path(conversation_id)}/run",
            accepted_statuses=frozenset({409}),
        ).json()

    def pause(self, conversation_id=None) -> dict:
        return self._request("POST", f"{self._conversation_path(conversation_id)}/pause").json()

    def get_conversation(self, conversation_id=None) -> dict:
        """GET ConversationInfo：含 execution_status 与 stats.usage_to_metrics。"""
        return self._request("GET", self._conversation_path(conversation_id)).json()

    # ------------------------------------------------------------------
    # 事件
    # ------------------------------------------------------------------
    def search_events(
        self,
        *,
        kind: str | None = None,
        source: str | None = None,
        after_id: str | None = None,
        conversation_id=None,
    ) -> list[dict]:
        """拉取事件（全量分页，TIMESTAMP 升序）。

        after_id 给定时，只返回该事件之后的新事件（客户端过滤）。
        """
        items: list[dict] = []
        page_id: str | None = None
        while True:
            params: dict = {"limit": EVENTS_PAGE_LIMIT, "sort_order": "TIMESTAMP"}
            if page_id:
                params["page_id"] = page_id
            if kind:
                params["kind"] = kind
            if source:
                params["source"] = source
            page = self._request(
                "GET", f"{self._conversation_path(conversation_id)}/events/search", params=params
            ).json()
            items.extend(page.get("items", []))
            page_id = page.get("next_page_id")
            if not page_id:
                break
        if after_id is not None:
            for i, ev in enumerate(items):
                if ev.get("id") == after_id:
                    return items[i + 1:]
            return items  # after_id 未找到（崩溃恢复）：返回全量
        return items

    # ------------------------------------------------------------------
    # Bash / Git / 文件
    # ------------------------------------------------------------------
    def execute_bash(self, command: str, *, timeout: int = 300, cwd: str | None = None) -> dict:
        """ExecuteBashRequest -> BashOutput{id, command_id, exit_code, stdout, stderr, kind}。"""
        body: dict = {"command": command, "timeout": timeout}
        if cwd:
            body["cwd"] = cwd
        return self._request("POST", "/api/bash/execute_bash_command", json=body).json()

    def git_diff(self, path: str) -> dict:
        """GET /api/git/diff/{path} -> GitDiff{modified, original}。"""
        return self._request("GET", f"/api/git/diff/{path}").json()

    def upload_file(self, path: str, content: bytes) -> dict:
        return self._request(
            "POST", f"/api/file/upload/{path}", files={"file": content}
        ).json()

    # ------------------------------------------------------------------
    # 等待运行结束（orchestrator 的单 step 近似驱动）
    # ------------------------------------------------------------------
    def wait_until_idle(
        self,
        *,
        timeout_seconds: float = 300.0,
        poll_interval: float = 2.0,
        require_execution_start: bool = False,
        start_timeout_seconds: float = 15.0,
        conversation_id=None,
    ) -> dict:
        """Wait for a scheduled execution to start and then become idle.

        OpenHands schedules conversation runs asynchronously, so the first poll
        can still expose the pre-run ``idle`` or stale ``finished`` state.
        Server-transport callers opt into start synchronization; either state is
        accepted only after a running state or completed usage has been observed.
        """
        started_at = time.monotonic()
        deadline = started_at + timeout_seconds
        start_deadline = started_at + min(start_timeout_seconds, timeout_seconds)
        execution_started = not require_execution_start
        info: dict = {}
        while True:
            now = time.monotonic()
            if now >= deadline:
                break
            info = self.get_conversation(conversation_id)
            status = info.get("execution_status", "idle")
            if status not in IDLE_STATUSES:
                execution_started = True
            elif (
                status not in AMBIGUOUS_PRE_START_STATUSES
                or execution_started
                or self._has_completed_usage(info)
            ):
                return info
            if require_execution_start and not execution_started and now >= start_deadline:
                raise AgentServerError(
                    f"conversation did not start within {start_timeout_seconds}s "
                    f"(last status: {status!r})"
                )
            time.sleep(poll_interval)
        raise AgentServerError(
            f"conversation still running after {timeout_seconds}s "
            f"(last status: {info.get('execution_status')!r})"
        )

    @staticmethod
    def _has_completed_usage(info: dict) -> bool:
        usage_to_metrics = ((info.get("stats") or {}).get("usage_to_metrics") or {})
        for metrics in usage_to_metrics.values():
            if not isinstance(metrics, dict):
                continue
            if metrics.get("token_usages"):
                return True
        return False
