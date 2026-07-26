from __future__ import annotations

import json
import os
import uuid
from pathlib import Path

import pytest

from app.core.config import settings
from app.execution_engines import adapter_for
from app.worker.cli_client import CLIEngineClient, engine_environment
from app.worker.local_workspace import LocalWorkspaceManager
from app.worker.orchestrator import Orchestrator
from app.worker.workspace_manager import WorkspaceError

pytestmark = pytest.mark.unit


class FakeProcess:
    def __init__(self, stdout: str, stderr: str = "", returncode: int = 0):
        self._stdout = stdout
        self._stderr = stderr
        self.returncode = returncode
        self.pid = 12345

    def poll(self):
        return self.returncode

    def communicate(self, timeout=None):
        del timeout
        return self._stdout, self._stderr


def test_codex_client_runs_bounded_turn_and_exposes_only_public_events(tmp_path: Path) -> None:
    lines = [
        {"type": "thread.started", "thread_id": "thread-1"},
        {"type": "item.completed", "item": {"id": "hidden", "type": "reasoning", "text": "secret"}},
        {"type": "item.completed", "item": {"id": "msg", "type": "agent_message", "text": "done"}},
        {
            "type": "item.completed",
            "item": {
                "id": "tool-1",
                "type": "command_execution",
                "command": "rm -rf /tmp/outside",
                "aggregated_output": "blocked by policy review fixture",
                "exit_code": 0,
                "status": "completed",
            },
        },
        {
            "type": "turn.completed",
            "usage": {
                "input_tokens": 12,
                "cached_input_tokens": 2,
                "output_tokens": 7,
                "reasoning_output_tokens": 3,
            },
        },
    ]
    captured: dict = {}

    def factory(command, **kwargs):
        captured["command"] = command
        captured["env"] = kwargs["env"]
        return FakeProcess("\n".join(json.dumps(line) for line in lines))

    client = CLIEngineClient(
        adapter_for("codex"),
        str(tmp_path),
        model="gpt-5",
        process_factory=factory,
    )
    conversation_id = uuid.uuid4()
    client.create_conversation(
        model="gpt-5",
        llm_base_url="",
        llm_api_key="",
        working_dir=str(tmp_path),
        initial_message="task",
        conversation_id=conversation_id,
    )
    client.send_message("finish")
    info = client.wait_until_idle(timeout_seconds=5)

    assert captured["command"][:5] == ["codex", "exec", "--json", "--sandbox", "workspace-write"]
    assert info["execution_status"] == "finished"
    assert info["stats"]["usage_to_metrics"]["agent"]["token_usages"][0]["prompt_tokens"] == 12
    events = client.search_events()
    assert {event["kind"] for event in events} == {"MessageEvent", "ActionEvent", "ObservationEvent"}
    serialized = json.dumps(events)
    assert "done" in serialized
    assert "secret" not in serialized
    assert client.native_session_id == "thread-1"

    run = type("Run", (), {"current_phase": "modify"})()
    orchestrator = Orchestrator(type("Session", (), {"add": lambda _self, _item: None})(), uuid.uuid4())
    orchestrator.emit_event = lambda *_args, **_kwargs: None
    orchestrator._put_artifact = lambda *_args, **_kwargs: "artifact"
    observed = orchestrator._record_events(run, 1, events)
    assert observed["risk_hits"]
    calls, tokens, cost = orchestrator._record_llm_calls(run, 1, info)
    assert len(calls) == 1
    assert tokens == 19
    assert cost == 0


def test_engine_environment_passes_only_engine_scoped_secrets(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(settings, "cli_engine_state_root", str(tmp_path / "state"))
    monkeypatch.setenv("OPENAI_API_KEY", "must-not-leak")
    monkeypatch.setenv("BUDGETLOOP_CODEX_ENV_OPENAI_API_KEY", "codex-only")
    monkeypatch.setenv("BUDGETLOOP_GEMINI_CLI_ENV_GEMINI_API_KEY", "gemini-only")
    environment = engine_environment("codex")
    assert environment["OPENAI_API_KEY"] == "codex-only"
    assert "GEMINI_API_KEY" not in environment
    assert environment["HOME"].endswith("/codex")


def test_managed_gemini_environment_maps_only_native_runtime_values(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(settings, "cli_engine_state_root", str(tmp_path / "state"))
    runtime = {
        "OPENAI_BASE_URL": "http://control-plane/runtime/v1",
        "OPENAI_API_KEY": "scoped-token",
        "OPENAI_MODEL": "deepseek-model",
        "GOOGLE_GEMINI_BASE_URL": "http://control-plane/runtime",
        "GEMINI_API_KEY": "scoped-token",
        "GEMINI_MODEL": "deepseek-model",
        "BUDGETLOOP_AI_MANAGED": "1",
        "UNSAFE": "do-not-copy",
    }
    environment = engine_environment("gemini-cli", runtime_env=runtime)
    assert environment["GOOGLE_GEMINI_BASE_URL"] == "http://control-plane/runtime"
    assert environment["GEMINI_API_KEY"] == "scoped-token"
    assert environment["GEMINI_MODEL"] == "deepseek-model"
    assert "OPENAI_API_KEY" not in environment
    assert "UNSAFE" not in environment


def test_cli_client_real_subprocess_smoke(monkeypatch, tmp_path: Path) -> None:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    executable = bin_dir / "codex"
    executable.write_text(
        "#!/bin/sh\n"
        "printf '%s\\n' "
        '\'{"type":"thread.started","thread_id":"smoke-thread"}\' '
        '\'{"type":"item.completed","item":{"id":"m1","type":"agent_message","text":"smoke ok"}}\' '
        '\'{"type":"turn.completed","usage":{"input_tokens":1,"output_tokens":1}}\'\n',
        encoding="utf-8",
    )
    executable.chmod(0o755)
    monkeypatch.setenv("PATH", f"{bin_dir}:{os.environ.get('PATH', '')}")
    monkeypatch.setattr(settings, "cli_engine_state_root", str(tmp_path / "state"))
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    client = CLIEngineClient(adapter_for("codex"), str(workspace), timeout=5)
    client.create_conversation(
        model="",
        llm_base_url="",
        llm_api_key="",
        working_dir=str(workspace),
        initial_message="task",
        conversation_id=uuid.uuid4(),
    )
    client.send_message("execute")
    assert client.wait_until_idle(timeout_seconds=5)["execution_status"] == "finished"
    assert "smoke ok" in json.dumps(client.search_events())


def test_local_workspace_copies_source_and_creates_owned_worktree(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "README.md").write_text("hello", encoding="utf-8")
    root = tmp_path / "workspaces"
    manager = LocalWorkspaceManager(root)
    run_id = str(uuid.uuid4())
    session_id = str(uuid.uuid4())
    handle = manager.provision(run_id, source_dir=source, worktree_session_id=session_id)
    assert handle.container_id == f"local:{uuid.UUID(run_id).hex}"
    assert handle.worktree_branch and handle.worktree_branch.startswith("bl/session-")
    assert Path(handle.working_dir, "README.md").read_text(encoding="utf-8") == "hello"
    attached = manager.attach(
        run_id,
        handle.container_id,
        working_dir=handle.working_dir,
        worktree_branch=handle.worktree_branch,
    )
    assert attached.working_dir == handle.working_dir


def test_local_workspace_rejects_external_symlink(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    outside = tmp_path / "outside.txt"
    outside.write_text("private", encoding="utf-8")
    (source / "escape").symlink_to(outside)
    manager = LocalWorkspaceManager(tmp_path / "workspaces")
    with pytest.raises(WorkspaceError, match="external symlink"):
        manager.provision(str(uuid.uuid4()), source_dir=source)
