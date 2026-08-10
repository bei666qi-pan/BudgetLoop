"""Stable engine command/event adapters; business authority remains in BudgetLoop."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Protocol

from app.execution_engines.registry import ExecutionEngine, get_engine


class InjectionPoint(Enum):
    NONE = "none"
    ITERATION_START = "iteration_start"
    ITERATION_END = "iteration_end"


@dataclass
class ExtractedProgressSignal:
    """Structured progress declaration parsed from agent output — agent-declared, not inferred."""

    summary: str | None = None
    milestone: str | None = None
    completed_items: list[str] = field(default_factory=list)
    next_step: str | None = None
    blocked: bool = False
    blocker_reason: str | None = None
    needs_operator: bool = False
    evidence: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "summary": self.summary,
            "milestone": self.milestone,
            "completed_items": self.completed_items,
            "next_step": self.next_step,
            "blocked": self.blocked,
            "blocker_reason": self.blocker_reason,
            "needs_operator": self.needs_operator,
            "evidence": self.evidence,
        }


def _mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _ensure_str_list(value: Any) -> list[str]:
    """Normalize a JSON value into a list of strings for completed_items."""
    if isinstance(value, list):
        return [str(item) for item in value if item is not None]
    if isinstance(value, str):
        return [value]
    return []


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
        writable_dirs: tuple[str, ...] = (),
        sandbox_mode: str = "workspace-write",
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
        writable_dirs: tuple[str, ...] = (),
        sandbox_mode: str = "workspace-write",
    ) -> list[str]:
        command = self.engine.command or self.engine.id
        if self.engine.id == "codex":
            args = [
                command,
                "exec",
                "--json",
                "--sandbox",
                sandbox_mode,
                "--skip-git-repo-check",
                "-C",
                workdir,
            ]
            if model:
                args.extend(["-m", model])
            for directory in writable_dirs:
                args.extend(["--add-dir", directory])
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
            writable_dirs=tuple(model_config.get("_server_writable_dirs") or ()),
            sandbox_mode=str(model_config.get("_server_codex_sandbox") or "workspace-write"),
        )

    # ------------------------------------------------------------------
    # CLI safety-checkpoint injection and progress extraction
    # ------------------------------------------------------------------

    def check_injection_point(
        self, events: list[NormalizedEngineEvent]
    ) -> InjectionPoint:
        """Detect iteration start/end boundaries from normalized events.

        CLI engines cannot receive hot-injected messages mid-stream.  Messages
        are injected at iteration boundaries — specifically at ITERATION_START,
        before the next prompt is dispatched.  This method analyses normalized
        events to determine whether the engine is entering or leaving an
        iteration.

        Returns ITERATION_START when the most recent event is a start signal
        (or no events yet — fresh start).  Returns ITERATION_END when the
        most recent event is terminal.  Returns NONE when events are in the
        middle of an active iteration.
        """
        if not events:
            return InjectionPoint.ITERATION_START

        terminal_kinds: dict[str, set[str]] = {
            "codex": {"turn.completed", "turn.failed"},
            "gemini-cli": {"result"},
            "opencode": {"step_finish"},
        }
        start_kinds: dict[str, set[str]] = {
            "codex": {"thread.started"},
            "gemini-cli": {"init"},
            "opencode": set(),
        }

        terminal_set = terminal_kinds.get(self.engine.id, set())
        start_set = start_kinds.get(self.engine.id, set())

        # Walk events from last to first; the most recent boundary wins.
        # If we find a terminal as the last event → ITERATION_END.
        # If we find a start as the last meaningful event → ITERATION_START.
        # If the last event is neither, we are mid-iteration → NONE.
        found_mid = False
        for ev in reversed(events):
            if ev.kind in terminal_set or ev.terminal:
                return InjectionPoint.ITERATION_END if not found_mid else InjectionPoint.NONE
            if ev.kind in start_set:
                return InjectionPoint.ITERATION_START if not found_mid else InjectionPoint.NONE
            found_mid = True

        return InjectionPoint.NONE

    def extract_progress_signal(self, text: str) -> ExtractedProgressSignal | None:
        """Parse structured progress from agent output text.

        Detects three forms:
        1. Explicit JSON block marked with ``[PROGRESS]`` prefix.
        2. Inline ``PROGRESS:`` key-value pairs.
        3. A JSON object containing progress-signal keys.

        Returns None when no structured progress signal is found.
        """
        if not text:
            return None

        # Form 1: [PROGRESS] { ... } JSON block
        progress_match = re.search(
            r"\[PROGRESS\]\s*(\{.*?\})\s*(?:$|\n)", text, re.DOTALL
        )
        if progress_match:
            return self._parse_progress_json(progress_match.group(1))

        # Form 2: Inline key-value pairs with PROGRESS: prefix
        inline_keys = {
            "summary", "milestone", "completed_items", "next_step",
            "blocked", "blocker_reason", "needs_operator", "evidence",
        }
        if any(f"PROGRESS:{key}" in text for key in inline_keys):
            return self._parse_progress_inline(text, inline_keys)

        # Form 3: Raw JSON object with progress keys
        try:
            trimmed = text.strip()
            if trimmed.startswith("{") and trimmed.endswith("}"):
                obj = json.loads(trimmed)
                if isinstance(obj, dict) and any(k in obj for k in inline_keys):
                    return self._parse_progress_json(trimmed)
        except json.JSONDecodeError:
            pass

        return None

    def detect_message_acknowledgement(
        self, events: list[NormalizedEngineEvent]
    ) -> set[str]:
        """Extract acknowledged message IDs from agent output events.

        Detects when an agent confirms receipt of injected messages via
        ``send_message``-style tool calls or structured output containing
        ``acknowledging_message_id`` references.

        Returns a set of confirmed message ID strings.
        """
        acknowledged: set[str] = set()
        for ev in events:
            text = ev.public_text or ""
            # Pattern 1: acknowledged_message_id / acknowledging_message_id
            for pattern in (
                r"acknowledg(?:ed|ing)_message_id[\"'\s:=]+([a-f0-9-]{32,36})",
                r'"message_ack"\s*:\s*\[(.*?)\]',
                r'"acknowledged_messages"\s*:\s*\[(.*?)\]',
            ):
                for match in re.finditer(pattern, text, re.IGNORECASE):
                    group = match.group(1)
                    ids = re.findall(r"[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}", group)
                    acknowledged.update(ids)

            # Pattern 2: send_message tool input with acknowledging_message_id
            tool_input = ev.tool_input or {}
            if isinstance(tool_input, dict):
                ack_id = tool_input.get("acknowledging_message_id") or tool_input.get("acknowledged_message_id")
                if ack_id and isinstance(ack_id, str):
                    acknowledged.add(ack_id)
                # Also check for list form
                ack_list = tool_input.get("acknowledged_messages") or tool_input.get("message_acks")
                if isinstance(ack_list, list):
                    for item in ack_list:
                        if isinstance(item, str) and len(item) >= 32:
                            acknowledged.add(item)

            # Pattern 3: Raw payload acknowledgement fields
            if ev.raw:
                ack = ev.raw.get("acknowledging_message_id") or ev.raw.get("acknowledged_message_id")
                if ack and isinstance(ack, str):
                    acknowledged.add(ack)

        return acknowledged

    # ------------------------------------------------------------------
    # Internal progress parsing helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_progress_json(json_text: str) -> ExtractedProgressSignal | None:
        try:
            obj = json.loads(json_text)
        except json.JSONDecodeError:
            return None
        if not isinstance(obj, dict):
            return None
        return ExtractedProgressSignal(
            summary=obj.get("summary"),
            milestone=obj.get("milestone"),
            completed_items=_ensure_str_list(obj.get("completed_items")),
            next_step=obj.get("next_step"),
            blocked=bool(obj.get("blocked", False)),
            blocker_reason=obj.get("blocker_reason"),
            needs_operator=bool(obj.get("needs_operator", False)),
            evidence=obj.get("evidence"),
        )

    @staticmethod
    def _parse_progress_inline(text: str, keys: set[str]) -> ExtractedProgressSignal | None:
        signal = ExtractedProgressSignal()
        found = False
        for key in keys:
            pattern = rf"PROGRESS:{key}\s*[:=]?\s*(.+?)(?:\n|PROGRESS:|$)"
            match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
            if match:
                value = match.group(1).strip()
                found = True
                if key == "completed_items":
                    items = [i.strip() for i in value.replace(";", ",").split(",") if i.strip()]
                    signal.completed_items = items
                elif key in ("blocked", "needs_operator"):
                    setattr(signal, key, value.lower() in ("true", "1", "yes"))
                else:
                    setattr(signal, key, value)
        return signal if found else None

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
        if kind == "message" and payload.get("role") == "assistant":
            event_kind = "message_delta" if payload.get("delta") else "message"
            return NormalizedEngineEvent(
                event_kind,
                str(payload.get("content") or "")[:2000],
                None,
                payload,
            )
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
