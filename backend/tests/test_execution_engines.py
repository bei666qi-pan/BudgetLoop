from __future__ import annotations

import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("SKIP_MIGRATIONS", "1")

from app.core.config import settings  # noqa: E402
from app.execution_engines import DEFAULT_ENGINE_ID, ENGINES, adapter_for, engine_preflight
from app.execution_engines.registry import PROJECT_ROOT, list_engines
from app.main import app  # noqa: E402
from app.worker.orchestrator import selected_execution_engine  # noqa: E402

pytestmark = pytest.mark.unit

EXPECTED_REVISIONS = {
    "openhands": "652503005093d18d1b2f48816c91d62e93f45970",
    "codex": "4c43465133428898aa84f0bfc02c306ed65fb66a",
    "gemini-cli": "3818efbbfbf8ef029ef53a6ab1093db39971ce83",
    "opencode": "7534d23551f665e65080809975b4ca5c7d63807b",
}


def test_registry_contains_pinned_high_star_engines_and_openhands_default() -> None:
    assert DEFAULT_ENGINE_ID == "openhands"
    assert {engine.id: engine.revision for engine in ENGINES} == EXPECTED_REVISIONS
    assert all(engine.reviewed_stars >= 10_000 for engine in ENGINES)
    assert {engine.license for engine in ENGINES} == {"MIT core", "MIT", "Apache-2.0"}
    assert all(len(engine.revision) == 40 for engine in ENGINES)
    distributions = {
        engine.id: (engine.distribution_package, engine.distribution_version)
        for engine in ENGINES
        if engine.distribution_package
    }
    assert distributions == {
        "codex": ("@openai/codex", "0.145.0"),
        "gemini-cli": ("@google/gemini-cli", "0.52.0"),
    }


def test_all_pinned_sources_are_downloaded_and_enterprise_is_excluded() -> None:
    for engine in ENGINES:
        checkout = PROJECT_ROOT / engine.source_path
        assert checkout.is_dir(), engine.id
        assert (checkout / ".git").exists(), engine.id
    assert not (PROJECT_ROOT / "vendor/agent-engines/openhands/enterprise").exists()


def test_catalog_distinguishes_source_downloaded_from_runtime_available() -> None:
    items = {item["id"]: item for item in list_engines()}
    assert all(item["source_downloaded"] for item in items.values())
    assert items["openhands"]["runtime_available"] is True
    assert items["openhands"]["default"] is True
    assert items["codex"]["source_downloaded"] is True
    assert isinstance(items["codex"]["package_installed"], bool)
    assert isinstance(items["codex"]["managed_ai_ready"], bool)
    assert items["openhands"]["package_installed"] is None
    assert items["openhands"]["managed_ai_ready"] is None
    assert items["codex"]["availability_reason"]
    assert engine_preflight("missing").runtime_available is False


def test_cli_engine_becomes_available_only_with_flag_binary_and_scoped_credentials(monkeypatch) -> None:
    monkeypatch.setattr(settings, "enable_cli_engines", True)
    monkeypatch.setattr("app.execution_engines.registry.shutil.which", lambda _command: "/usr/bin/codex")
    monkeypatch.setenv("BUDGETLOOP_CODEX_ENV_OPENAI_API_KEY", "engine-scoped-test-key")
    status = engine_preflight("codex")
    assert status.runtime_available is True
    assert "Worker 生命周期适配均已就绪" in status.reason
    assert selected_execution_engine({"execution_engine": "codex"}) == "codex"


def test_cli_engine_fails_closed_without_scoped_credentials(monkeypatch) -> None:
    monkeypatch.setattr(settings, "enable_cli_engines", True)
    monkeypatch.setattr(settings, "managed_ai_runtime_enabled", False)
    monkeypatch.setattr("app.execution_engines.registry.shutil.which", lambda _command: "/usr/bin/codex")
    monkeypatch.delenv("BUDGETLOOP_CODEX_HOME", raising=False)
    for name in tuple(os.environ):
        if name.startswith("BUDGETLOOP_CODEX_ENV_"):
            monkeypatch.delenv(name, raising=False)
    with pytest.raises(RuntimeError, match="独立凭据"):
        selected_execution_engine({"execution_engine": "codex"})


def test_managed_runtime_satisfies_codex_and_gemini_authentication(monkeypatch) -> None:
    monkeypatch.setattr(settings, "enable_cli_engines", True)
    monkeypatch.setattr(
        "app.execution_engines.registry.shutil.which",
        lambda command: f"/usr/bin/{command}",
    )
    monkeypatch.setattr(
        "app.execution_engines.registry._managed_credentials_configured",
        lambda engine_id: engine_id in {"codex", "gemini-cli"},
    )
    monkeypatch.setenv("BUDGETLOOP_GEMINI_CLI_SANDBOX_READY", "true")
    assert engine_preflight("codex").runtime_available is True
    assert engine_preflight("gemini-cli").runtime_available is True
    assert "BudgetLoop 受管 AI" in engine_preflight("codex").reason


def test_opencode_requires_explicit_outer_sandbox_or_host_opt_in(monkeypatch) -> None:
    monkeypatch.setattr(settings, "enable_cli_engines", True)
    monkeypatch.setattr("app.execution_engines.registry.shutil.which", lambda _command: "/usr/bin/opencode")
    monkeypatch.setenv("BUDGETLOOP_OPENCODE_ENV_ANTHROPIC_API_KEY", "engine-scoped-test-key")
    monkeypatch.delenv("BUDGETLOOP_OPENCODE_SANDBOX_COMMAND", raising=False)
    monkeypatch.delenv("BUDGETLOOP_OPENCODE_ALLOW_HOST_EXECUTION", raising=False)
    assert engine_preflight("opencode").runtime_available is False
    monkeypatch.setenv("BUDGETLOOP_OPENCODE_ALLOW_HOST_EXECUTION", "true")
    assert engine_preflight("opencode").runtime_available is True


def test_legacy_run_resolves_to_openhands() -> None:
    assert selected_execution_engine({}) == "openhands"


@pytest.mark.parametrize(
    ("engine_id", "expected"),
    [
        ("codex", ["codex", "exec", "--json", "--sandbox", "workspace-write"]),
        ("gemini-cli", ["gemini", "-p", "ship it", "--output-format", "stream-json"]),
        ("opencode", ["opencode", "run", "--format", "json", "--dir", "/workspace"]),
    ],
)
def test_cli_adapters_build_auditable_noninteractive_commands(engine_id: str, expected: list[str]) -> None:
    command = adapter_for(engine_id).build_command(prompt="ship it", workdir="/workspace")
    assert command[: len(expected)] == expected
    assert "ship it" in command


def test_event_normalization_drops_hidden_reasoning_but_keeps_public_output() -> None:
    adapter = adapter_for("codex")
    assert (
        adapter.normalize_json_line(
            '{"type":"item.completed","item":{"id":"r1","type":"reasoning","text":"private"}}'
        )
        is None
    )
    event = adapter.normalize_json_line(
        '{"type":"item.completed","item":{"id":"m1","type":"agent_message","text":"public result"}}'
    )
    assert event is not None
    assert event.public_text == "public result"
    diagnostic = adapter.normalize_json_line("plain stderr")
    assert diagnostic is not None
    assert diagnostic.kind == "diagnostic"


def test_fetch_script_pins_every_manifest_revision() -> None:
    script = (PROJECT_ROOT / "scripts/fetch-agent-engines.sh").read_text(encoding="utf-8")
    for revision in EXPECTED_REVISIONS.values():
        assert revision in script
    assert "!/enterprise/" in script
    assert Path(PROJECT_ROOT / "vendor/agent-engines/README.md").is_file()


def test_authenticated_engine_catalog_discloses_control_plane_authority() -> None:
    with TestClient(app) as client:
        assert client.get("/api/execution-engines").status_code == 401
        response = client.get(
            "/api/execution-engines",
            headers={"Authorization": f"Bearer {settings.api_token}"},
        )
    assert response.status_code == 200
    payload = response.json()
    assert payload["default_engine"] == "openhands"
    assert payload["authority"] == {
        "control_plane": "BudgetLoop",
        "durable_state": "PostgreSQL",
        "engines_are_replaceable": True,
        "silent_fallback": False,
    }
