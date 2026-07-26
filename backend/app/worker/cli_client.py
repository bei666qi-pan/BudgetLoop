"""Bounded CLI execution client exposing the OpenHands-compatible worker surface."""

from __future__ import annotations

import json
import os
import shlex
import signal
import subprocess
import time
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import Any

from app.core.config import settings
from app.execution_engines.adapters import CLIEngineAdapter, NormalizedEngineEvent


class CLIEngineError(RuntimeError):
    """A CLI engine failed preflight, execution or output normalization."""


ProcessFactory = Callable[..., subprocess.Popen[str]]


class CLIEngineClient:
    """Run one non-interactive engine turn with a hard timeout and public events."""

    transport = "cli"

    def __init__(
        self,
        adapter: CLIEngineAdapter,
        working_dir: str,
        *,
        model: str | None = None,
        timeout: float = 300.0,
        process_factory: ProcessFactory = subprocess.Popen,
        runtime_env: dict[str, str] | None = None,
    ):
        self.adapter = adapter
        self.engine = adapter.engine
        self.working_dir = str(Path(working_dir).resolve())
        self.model = model
        self.timeout = timeout
        self.process_factory = process_factory
        self.runtime_env = dict(runtime_env or {})
        self.conversation_id: uuid.UUID | None = None
        self.native_session_id: str | None = None
        self.initial_message: str | None = None
        self._process: subprocess.Popen[str] | None = None
        self._events: list[dict[str, Any]] = []
        self._usages: list[dict[str, Any]] = []
        self._latencies: list[float] = []
        self._execution_status = "idle"
        self._last_public_error: str | None = None
        self._has_run = False
        self._state_dir = Path(self.working_dir) / ".budgetloop"
        self._state_file = self._state_dir / f"{self.engine.id}-session.json"
        self._event_file = self._state_dir / f"{self.engine.id}-events.jsonl"

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
        del llm_base_url, llm_api_key, max_iterations, usage_id, extra_llm
        resolved = Path(working_dir).resolve()
        if resolved != Path(self.working_dir):
            raise CLIEngineError("CLI conversation working directory changed after provisioning")
        self.model = model or self.model
        self.conversation_id = conversation_id or uuid.uuid4()
        self.initial_message = initial_message
        self._state_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        self._load_state()
        return {
            "id": str(self.conversation_id),
            "execution_status": self._execution_status,
            "engine": self.engine.id,
        }

    def send_message(self, text: str, *, run: bool = True, conversation_id=None) -> dict:
        if not run:
            raise CLIEngineError("CLI turns must be explicitly executed")
        if conversation_id is not None:
            self.conversation_id = uuid.UUID(str(conversation_id))
        if self.conversation_id is None:
            raise CLIEngineError("conversation_id not set; call create_conversation first")
        if self._process is not None and self._process.poll() is None:
            raise CLIEngineError("CLI engine is already running")

        prompt = text
        if not self._has_run and self.initial_message:
            prompt = f"{self.initial_message}\n\n# 本次有界执行\n{text}"
        session_id = self.native_session_id
        if self.engine.id == "gemini-cli" and session_id is None:
            session_id = str(self.conversation_id)
        command = self.adapter.build_command(
            prompt=prompt,
            workdir=self.working_dir,
            session_id=session_id,
            model=self.model,
            is_resume=self._has_run and bool(self.native_session_id),
        )
        self._execution_status = "running"
        self._last_public_error = None
        self._started_at = time.monotonic()
        environment = engine_environment(self.engine.id, runtime_env=self.runtime_env)
        sandbox = environment.pop("BUDGETLOOP_ENGINE_SANDBOX_COMMAND", None)
        if sandbox:
            command = [*shlex.split(sandbox), *command]
        self._process = self.process_factory(
            command,
            cwd=self.working_dir,
            env=environment,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            start_new_session=True,
        )
        return {"accepted": True, "engine": self.engine.id}

    def wait_until_idle(self, *, timeout_seconds: float | None = None, **_kwargs) -> dict:
        if self._process is None:
            return self._conversation_info()
        timeout = min(float(timeout_seconds or self.timeout), self.timeout)
        try:
            stdout, stderr = self._process.communicate(timeout=timeout)
        except subprocess.TimeoutExpired as exc:
            self.cancel()
            raise CLIEngineError(f"{self.engine.name} exceeded the {timeout:.0f}s step timeout") from exc
        latency = max(0.0, time.monotonic() - self._started_at)
        returncode = int(self._process.returncode or 0)
        self._process = None
        self._has_run = True
        self._latencies.append(latency)
        self._parse_output(stdout, stderr, failed=returncode != 0)
        if returncode != 0:
            self._execution_status = "error"
            reason = self._last_public_error or stderr.strip() or stdout.strip() or f"exit {returncode}"
            raise CLIEngineError(f"{self.engine.name} failed: {reason[:1000]}")
        self._execution_status = "finished"
        self._save_state()
        return self._conversation_info()

    def search_events(
        self,
        *,
        kind: str | None = None,
        source: str | None = None,
        after_id: str | None = None,
        conversation_id=None,
    ) -> list[dict[str, Any]]:
        del conversation_id
        events = self._events
        if kind:
            events = [event for event in events if event.get("kind") == kind]
        if source:
            events = [event for event in events if event.get("source") == source]
        if after_id is not None:
            for index, event in enumerate(events):
                if event.get("id") == after_id:
                    return events[index + 1 :]
        return list(events)

    def execute_bash(self, command: str, *, timeout: int = 300, cwd: str | None = None) -> dict:
        selected_cwd = self._safe_cwd(cwd)
        completed = subprocess.run(
            ["/bin/sh", "-lc", command],
            cwd=selected_cwd,
            env=engine_environment(self.engine.id, runtime_env=self.runtime_env),
            check=False,
            capture_output=True,
            text=True,
            timeout=min(timeout, int(self.timeout)),
        )
        return {
            "exit_code": completed.returncode,
            "stdout": completed.stdout,
            "stderr": completed.stderr,
        }

    def git_diff(self, path: str) -> dict:
        selected_cwd = self._safe_cwd(path)
        completed = subprocess.run(
            ["git", "-C", selected_cwd, "diff", "HEAD"],
            check=False,
            capture_output=True,
            text=True,
            timeout=60,
        )
        if completed.returncode != 0:
            raise CLIEngineError(f"git diff failed: {completed.stderr[:500]}")
        return {"modified": completed.stdout, "original": ""}

    def pause(self, conversation_id=None) -> dict:
        del conversation_id
        self._terminate_process(signal.SIGTERM)
        self._execution_status = "paused"
        return {"paused": True}

    def cancel(self, conversation_id=None) -> dict:
        del conversation_id
        self._terminate_process(signal.SIGKILL)
        self._execution_status = "cancelled"
        return {"cancelled": True}

    def close(self) -> None:
        if self._process is not None and self._process.poll() is None:
            self.cancel()

    def _terminate_process(self, sig: signal.Signals) -> None:
        process = self._process
        if process is None or process.poll() is not None:
            self._process = None
            return
        try:
            os.killpg(process.pid, sig)
            process.wait(timeout=5)
        except (ProcessLookupError, subprocess.TimeoutExpired):
            process.kill()
        finally:
            self._process = None

    def _parse_output(self, stdout: str, stderr: str, *, failed: bool) -> None:
        pending_tools: dict[str, NormalizedEngineEvent] = {}
        message_deltas: list[str] = []
        for line in stdout.splitlines():
            normalized = self.adapter.normalize_json_line(line)
            if normalized is None:
                continue
            if normalized.session_id:
                self.native_session_id = normalized.session_id
            if normalized.usage:
                self._usages.append(
                    {
                        **normalized.usage,
                        "response_id": str(uuid.uuid4()),
                        "model": self.model,
                    }
                )
            if normalized.kind == "tool_start" and normalized.event_id:
                pending_tools[normalized.event_id] = normalized
                self._append_action(normalized)
            elif normalized.kind == "tool_result" and normalized.event_id:
                self._append_observation(normalized)
            elif normalized.kind == "tool":
                self._append_action(normalized)
                self._append_observation(normalized)
            elif normalized.kind == "message_delta" and normalized.public_text:
                message_deltas.append(normalized.public_text)
            elif normalized.kind in {"message", "error", "diagnostic"} and normalized.public_text:
                self._append_message(normalized.public_text)
            if normalized.kind in {"error", "result"} and normalized.public_text:
                self._last_public_error = normalized.public_text
        if message_deltas:
            self._append_message("".join(message_deltas)[:8000])
        diagnostic = stderr.strip()
        if diagnostic and failed:
            self._append_message(f"[{self.engine.name}] {diagnostic[:2000]}")

    def _append_action(self, event: NormalizedEngineEvent) -> None:
        event_id = event.event_id or str(uuid.uuid4())
        self._append_event(
            {
                "id": str(uuid.uuid4()),
                "kind": "ActionEvent",
                "tool_call_id": event_id,
                "tool_name": event.tool or "tool",
                "action": event.tool_input or {},
                "timestamp": self._timestamp(),
            }
        )

    def _append_observation(self, event: NormalizedEngineEvent) -> None:
        event_id = event.event_id or str(uuid.uuid4())
        self._append_event(
            {
                "id": str(uuid.uuid4()),
                "kind": "ObservationEvent",
                "tool_call_id": event_id,
                "observation": {
                    "output": event.tool_output,
                    "exit_code": event.exit_code,
                },
                "timestamp": self._timestamp(),
            }
        )

    def _append_message(self, text: str) -> None:
        self._append_event(
            {
                "id": str(uuid.uuid4()),
                "kind": "MessageEvent",
                "source": "agent",
                "llm_message": {"content": [{"type": "text", "text": text[:2000]}]},
                "timestamp": self._timestamp(),
            }
        )

    def _append_event(self, event: dict[str, Any]) -> None:
        self._events.append(event)
        self._state_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        with self._event_file.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(event, ensure_ascii=False, default=str) + "\n")

    def _conversation_info(self) -> dict[str, Any]:
        return {
            "id": str(self.conversation_id) if self.conversation_id else None,
            "execution_status": self._execution_status,
            "stats": {
                "usage_to_metrics": {
                    "agent": {
                        "model_name": self.model,
                        "token_usages": list(self._usages),
                        "costs": [],
                        "response_latencies": list(self._latencies),
                    }
                }
            },
        }

    def _safe_cwd(self, cwd: str | None) -> str:
        selected = Path(cwd or self.working_dir).resolve()
        root = Path(self.working_dir)
        if selected != root and root not in selected.parents:
            raise CLIEngineError("command cwd escapes the assigned CLI workspace")
        return str(selected)

    def _load_state(self) -> None:
        if not self._state_file.is_file():
            return
        try:
            payload = json.loads(self._state_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        if payload.get("conversation_id") == str(self.conversation_id):
            native = payload.get("native_session_id")
            self.native_session_id = str(native) if native else None
            self._has_run = bool(payload.get("has_run"))

    def _save_state(self) -> None:
        self._state_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        payload = {
            "conversation_id": str(self.conversation_id),
            "native_session_id": self.native_session_id,
            "has_run": self._has_run,
            "engine": self.engine.id,
        }
        self._state_file.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    @staticmethod
    def _timestamp() -> str:
        from datetime import UTC, datetime

        return datetime.now(UTC).isoformat()


def engine_environment(
    engine_id: str, *, runtime_env: dict[str, str] | None = None
) -> dict[str, str]:
    """Build a minimal engine-scoped environment without cross-engine secrets."""
    key = engine_id.upper().replace("-", "_")
    prefix = f"BUDGETLOOP_{key}_ENV_"
    state_root = Path(settings.cli_engine_state_root).expanduser().resolve()
    configured_home = os.environ.get(f"BUDGETLOOP_{key}_HOME")
    home = Path(configured_home).expanduser().resolve() if configured_home else state_root / engine_id
    home.mkdir(parents=True, exist_ok=True, mode=0o700)
    allowed_base = {
        "PATH",
        "LANG",
        "LC_ALL",
        "TMPDIR",
        "SHELL",
        "SSL_CERT_FILE",
        "SSL_CERT_DIR",
        "HTTP_PROXY",
        "HTTPS_PROXY",
        "NO_PROXY",
    }
    environment = {name: value for name, value in os.environ.items() if name in allowed_base}
    environment["HOME"] = str(home)
    if engine_id == "codex":
        environment["CODEX_HOME"] = str(home)
    elif engine_id == "gemini-cli":
        environment["GEMINI_CLI_HOME"] = str(home)
        sandbox_image = os.environ.get("GEMINI_SANDBOX_IMAGE")
        if sandbox_image:
            environment["GEMINI_SANDBOX_IMAGE"] = sandbox_image
    elif engine_id == "opencode":
        environment["XDG_CONFIG_HOME"] = str(home / "config")
        environment["XDG_DATA_HOME"] = str(home / "data")
        environment["XDG_CACHE_HOME"] = str(home / "cache")
    for name, value in os.environ.items():
        if name.startswith(prefix) and len(name) > len(prefix):
            environment[name[len(prefix) :]] = value
    sandbox = os.environ.get(f"BUDGETLOOP_{key}_SANDBOX_COMMAND")
    if sandbox:
        environment["BUDGETLOOP_ENGINE_SANDBOX_COMMAND"] = " ".join(shlex.split(sandbox))
    managed = (runtime_env or {}).get("BUDGETLOOP_AI_MANAGED") == "1"
    if managed:
        environment["BUDGETLOOP_AI_MANAGED"] = "1"
        if engine_id == "codex":
            for name in ("OPENAI_BASE_URL", "OPENAI_API_KEY", "OPENAI_MODEL"):
                value = (runtime_env or {}).get(name)
                if value:
                    environment[name] = value
            _write_managed_codex_config(home, environment)
        elif engine_id == "gemini-cli":
            for name in (
                "GEMINI_API_KEY",
                "GEMINI_API_KEY_AUTH_MECHANISM",
                "GEMINI_MODEL",
            ):
                value = (runtime_env or {}).get(name)
                if value:
                    environment[name] = value
            gemini_base_url = (runtime_env or {}).get(
                "BUDGETLOOP_AI_CONTAINER_GEMINI_BASE_URL"
            ) or (runtime_env or {}).get("GOOGLE_GEMINI_BASE_URL")
            if gemini_base_url:
                environment["GOOGLE_GEMINI_BASE_URL"] = gemini_base_url
            # Gemini CLI 0.52 forwards only an allowlist into its Docker
            # sandbox. Its documented SANDBOX_ENV hook is therefore required
            # to preserve BudgetLoop's bearer auth mechanism after relaunch.
            environment["SANDBOX_ENV"] = "GEMINI_API_KEY_AUTH_MECHANISM=bearer"
            _write_managed_gemini_config(home)
    return environment


def _write_managed_codex_config(home: Path, environment: dict[str, str]) -> None:
    """Configure a secret-free Responses provider in Codex's isolated home."""
    base_url = environment.get("OPENAI_BASE_URL")
    model = environment.get("OPENAI_MODEL")
    if not base_url or not model or not environment.get("OPENAI_API_KEY"):
        return
    config = (
        f"model = {json.dumps(model)}\n"
        'model_provider = "budgetloop"\n'
        'model_reasoning_effort = "xhigh"\n\n'
        '[model_providers.budgetloop]\n'
        'name = "BudgetLoop Managed AI"\n'
        f"base_url = {json.dumps(base_url)}\n"
        'env_key = "OPENAI_API_KEY"\n'
        'wire_api = "responses"\n'
        'requires_openai_auth = false\n'
        'supports_websockets = false\n'
    )
    path = home / "config.toml"
    temporary = home / ".config.toml.tmp"
    temporary.write_text(config, encoding="utf-8")
    temporary.chmod(0o600)
    temporary.replace(path)


def _write_managed_gemini_config(home: Path) -> None:
    """Select Gemini API-key auth without persisting the run capability."""
    config_dir = home / ".gemini"
    config_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    path = config_dir / "settings.json"
    temporary = config_dir / ".settings.json.tmp"
    temporary.write_text(
        json.dumps(
            {"security": {"auth": {"selectedType": "gemini-api-key"}}},
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    temporary.chmod(0o600)
    temporary.replace(path)
