"""Stable engine command/event adapters; business authority remains in BudgetLoop."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Protocol

from app.execution_engines.registry import ExecutionEngine, get_engine


def _mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


@dataclass(frozen=True)
class NormalizedEngineEvent:
    kind: str
    public_text: str | None
    tool: str | None
    raw: dict[str, Any]
    event_id: str | None = None
    tool_input: Any = None
    tool_output: Any = None
    exit_code: int | None = None
    usage: dict[str, int] | None = None
    session_id: str | None = None
    terminal: bool = False


class ExecutionEngineAdapter(Protocol):
    engine: ExecutionEngine

    def build_command(
        self,
        *,
        prompt: str,
        workdir: str,
        session_id: str | None = None,
        model: str | None = None,
        is_resume: bool = False,
    ) -> list[str]: ...

    def normalize_json_line(self, line: str) -> NormalizedEngineEvent | None: ...

    def create_workspace_manager(self): ...

    def create_client(self, handle, model_config: dict[str, Any]): ...


class CLIEngineAdapter:
    def __init__(self, engine: ExecutionEngine):
        self.engine = engine

    def build_command(
        self,
        *,
        prompt: str,
        workdir: str,
        session_id: str | None = None,
        model: str | None = None,
        is_resume: bool = False,
    ) -> list[str]:
        command = self.engine.command or self.engine.id
        if self.engine.id == "codex":
            args = [
                command,
                "exec",
                "--json",
                "--sandbox",
                "workspace-write",
                "--skip-git-repo-check",
                "-C",
                workdir,
            ]
            if model:
                args.extend(["-m", model])
            if session_id and is_resume:
                args.extend(["resume", session_id])
            args.append(prompt)
            return args
        if self.engine.id == "gemini-cli":
            args = [
                command,
                "-p",
                prompt,
                "--output-format",
                "stream-json",
                "--sandbox",
                "--approval-mode",
                "auto_edit",
                "--skip-trust",
            ]
            if model:
                args.extend(["--model", model])
            if session_id and is_resume:
                args.extend(["--resume", "latest"])
            elif session_id:
                args.extend(["--session-id", session_id])
            return args
        if self.engine.id == "opencode":
            args = [command, "run", "--format", "json", "--dir", workdir, "--auto"]
            if model:
                args.extend(["--model", model])
            if session_id and is_resume:
                args.extend(["--session", session_id])
            args.append(prompt)
            return args
        raise ValueError(f"engine {self.engine.id!r} does not use the CLI adapter")

    def normalize_json_line(self, line: str) -> NormalizedEngineEvent | None:
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            return NormalizedEngineEvent("diagnostic", line[:2000], None, {"text": line[:2000]})
        if not isinstance(payload, dict):
            return None
        kind = str(payload.get("type") or payload.get("kind") or "event")
        lowered = kind.lower()
        if "thought" in lowered or "reasoning" in lowered:
            return None
        if self.engine.id == "codex":
            return self._normalize_codex(payload, kind)
        if self.engine.id == "gemini-cli":
            return self._normalize_gemini(payload, kind)
        if self.engine.id == "opencode":
            return self._normalize_opencode(payload, kind)
        tool = payload.get("tool") or payload.get("tool_name")
        text = payload.get("text") or payload.get("message") or payload.get("content")
        if isinstance(text, dict):
            text = text.get("text")
        public_text = str(text)[:2000] if isinstance(text, (str, int, float)) else None
        return NormalizedEngineEvent(kind, public_text, str(tool) if tool else None, payload)

    def create_workspace_manager(self):
        from app.worker.local_workspace import LocalWorkspaceManager

        return LocalWorkspaceManager()

    def create_client(self, handle, model_config: dict[str, Any]):
        from app.worker.cli_client import CLIEngineClient

        return CLIEngineClient(
            self,
            handle.working_dir,
            model=model_config.get("model"),
            timeout=float(model_config.get("agent_step_timeout", 300)),
            runtime_env=handle.runtime_env,
        )

    @staticmethod
    def _normalize_codex(payload: dict[str, Any], kind: str) -> NormalizedEngineEvent | None:
        if kind == "thread.started":
            session_id = payload.get("thread_id")
            return NormalizedEngineEvent(
                kind, None, None, payload, session_id=str(session_id) if session_id else None
            )
        if kind == "turn.completed":
            usage = _mapping(payload.get("usage"))
            normalized_usage = {
                "prompt_tokens": int(usage.get("input_tokens") or 0),
                "completion_tokens": int(usage.get("output_tokens") or 0),
                "reasoning_tokens": int(usage.get("reasoning_output_tokens") or 0),
                "cache_read_tokens": int(usage.get("cached_input_tokens") or 0),
                "cache_write_tokens": int(usage.get("cache_write_input_tokens") or 0),
            }
            return NormalizedEngineEvent(kind, None, None, payload, usage=normalized_usage, terminal=True)
        if kind in {"turn.failed", "error"}:
            error = payload.get("error")
            text = error.get("message") if isinstance(error, dict) else payload.get("message")
            return NormalizedEngineEvent(
                kind, str(text or "Codex execution failed")[:2000], None, payload, terminal=True
            )
        item = payload.get("item")
        if not isinstance(item, dict) or kind not in {"item.completed", "item.updated"}:
            return None
        item_type = str(item.get("type") or "")
        item_id = str(item.get("id") or "") or None
        if item_type == "reasoning":
            return None
        if item_type == "agent_message":
            return NormalizedEngineEvent(
                "message", str(item.get("text") or "")[:2000], None, payload, event_id=item_id
            )
        if item_type == "command_execution":
            return NormalizedEngineEvent(
                "tool",
                None,
                "execute_bash",
                payload,
                event_id=item_id,
                tool_input={"command": item.get("command")},
                tool_output=item.get("aggregated_output"),
                exit_code=item.get("exit_code") if isinstance(item.get("exit_code"), int) else None,
            )
        if item_type == "file_change":
            status = str(item.get("status") or "")
            return NormalizedEngineEvent(
                "tool",
                None,
                "apply_patch",
                payload,
                event_id=item_id,
                tool_input={"changes": item.get("changes") or []},
                tool_output={"status": status},
                exit_code=0 if status == "completed" else 1,
            )
        if item_type in {"mcp_tool_call", "collab_tool_call", "web_search"}:
            return NormalizedEngineEvent(
                "tool",
                None,
                item_type,
                payload,
                event_id=item_id,
                tool_input=item,
                tool_output={"status": item.get("status")},
                exit_code=0 if str(item.get("status")) == "completed" else None,
            )
        return None

    @staticmethod
    def _normalize_gemini(payload: dict[str, Any], kind: str) -> NormalizedEngineEvent | None:
        if kind == "init":
            session_id = payload.get("session_id")
            return NormalizedEngineEvent(
                kind, None, None, payload, session_id=str(session_id) if session_id else None
            )
        if kind == "message" and payload.get("role") == "assistant" and not payload.get("delta"):
            return NormalizedEngineEvent("message", str(payload.get("content") or "")[:2000], None, payload)
        if kind == "tool_use":
            return NormalizedEngineEvent(
                "tool_start",
                None,
                str(payload.get("tool_name") or "tool"),
                payload,
                event_id=str(payload.get("tool_id") or "") or None,
                tool_input=payload.get("parameters") or {},
            )
        if kind == "tool_result":
            error = payload.get("error")
            return NormalizedEngineEvent(
                "tool_result",
                None,
                None,
                payload,
                event_id=str(payload.get("tool_id") or "") or None,
                tool_output=payload.get("output") or error,
                exit_code=0 if payload.get("status") == "success" else 1,
            )
        if kind == "result":
            stats = _mapping(payload.get("stats"))
            usage = {
                "prompt_tokens": int(stats.get("input_tokens") or 0),
                "completion_tokens": int(stats.get("output_tokens") or 0),
                "cache_read_tokens": int(stats.get("cached") or 0),
            }
            error = payload.get("error")
            public_text = error.get("message") if isinstance(error, dict) else None
            return NormalizedEngineEvent(kind, public_text, None, payload, usage=usage, terminal=True)
        if kind == "error":
            return NormalizedEngineEvent(
                kind, str(payload.get("message") or "Gemini CLI error")[:2000], None, payload
            )
        return None

    @staticmethod
    def _normalize_opencode(payload: dict[str, Any], kind: str) -> NormalizedEngineEvent | None:
        session_id = payload.get("sessionID")
        if kind == "text":
            part = _mapping(payload.get("part"))
            return NormalizedEngineEvent(
                "message",
                str(part.get("text") or "")[:2000],
                None,
                payload,
                session_id=str(session_id) if session_id else None,
            )
        if kind == "tool_use":
            part = _mapping(payload.get("part"))
            state = _mapping(part.get("state"))
            return NormalizedEngineEvent(
                "tool",
                None,
                str(part.get("tool") or "tool"),
                payload,
                event_id=str(part.get("id") or "") or None,
                tool_input=state.get("input") or {},
                tool_output=state.get("output") or state.get("error"),
                exit_code=0 if state.get("status") == "completed" else 1,
                session_id=str(session_id) if session_id else None,
            )
        if kind == "step_finish":
            part = _mapping(payload.get("part"))
            tokens = _mapping(part.get("tokens"))
            cache = _mapping(tokens.get("cache"))
            usage = {
                "prompt_tokens": int(tokens.get("input") or 0),
                "completion_tokens": int(tokens.get("output") or 0),
                "reasoning_tokens": int(tokens.get("reasoning") or 0),
                "cache_read_tokens": int(cache.get("read") or 0),
            }
            return NormalizedEngineEvent(
                kind,
                None,
                None,
                payload,
                usage=usage,
                session_id=str(session_id) if session_id else None,
                terminal=True,
            )
        if kind == "error":
            return NormalizedEngineEvent(kind, "OpenCode execution failed", None, payload, terminal=True)
        return None


class OpenHandsEngineAdapter(CLIEngineAdapter):
    def build_command(self, **_kwargs) -> list[str]:
        raise ValueError("OpenHands uses the agent-server transport, not a local CLI command")

    def create_workspace_manager(self):
        from app.worker.workspace_manager import WorkspaceManager

        return WorkspaceManager()

    def create_client(self, handle, model_config: dict[str, Any]):
        del model_config
        from app.worker.openhands_client import AgentServerClient

        return AgentServerClient(handle.base_url, handle.session_key)


def adapter_for(engine_id: str) -> ExecutionEngineAdapter:
    engine = get_engine(engine_id)
    if engine is None:
        raise ValueError(f"unknown execution engine: {engine_id}")
    if engine.transport == "server":
        return OpenHandsEngineAdapter(engine)
    return CLIEngineAdapter(engine)
