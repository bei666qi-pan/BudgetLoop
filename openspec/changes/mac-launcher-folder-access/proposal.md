# Proposal: mac-launcher-folder-access

## Why

BudgetLoop today is a developer-grade stack: bringing it up means cloning the repo, hand-writing `.env`, running `docker compose`, and (for the default new-api gateway) manually clicking through a web console to configure an LLM channel before any run can execute. And no matter where the agent works, its edits are trapped inside a Docker volume — there is no way to point it at a real project folder on the Mac, which is the core Codex-style workflow users expect from a coding agent. Two gaps follow: (1) the product needs a double-clickable macOS app that owns the whole bring-up lifecycle; (2) tasks need a Codex-style permission model — isolated workspace by default, opt-in full-access that lets the agent edit a user-selected host folder directly.

## What Changes

- **New `BudgetLoop.app` all-in-one macOS launcher** (new `desktop/` project, Swift + WKWebView compiled with the system `swiftc`, no Xcode project required): detects/starts Docker Desktop, materializes `.env` from `.env.example` plus the user's locally saved AI-gateway settings (including the macOS Keychain credential), starts the required compose services, gates on health checks, opens a native window on the web UI, and stops the services it started when the window closes. Docker-absent, port-conflict, and gateway-unconfigured states produce readable native error pages; if a healthy stack is already running the app attaches to it instead of fighting it.
- **Codex-style folder permission modes on tasks** (modeled directly on OpenAI Codex's `SandboxMode` — `config_types.rs` in `vendor/agent-engines/codex` — not a novel invention; see the standing convention in `AGENTS.md`): task creation gains an optional host `project_dir` plus a `folder_access` mode — `isolated` (default, mirrors codex `workspace-write` inside the container boundary: agent writes only in the run's Docker volume, host folder untouched) or `full_access` (mirrors codex `danger-full-access`/`--add-dir`: the selected host folder is bind-mounted read-write at `/workspace` inside the agent container, so agent edits land directly in the folder, presented with the same loud high-risk signaling codex gives Full Access). The mode and folder are visible on the run detail page.
- **Gateway bootstrap automation**: when a compatible-gateway config exists in the user's local settings (`~/Library/Application Support/BudgetLoop/ai-gateway.json` + Keychain), the launcher injects it as `AI_GATEWAY_*` env for the compose stack — eliminating the manual new-api console step for that setup; otherwise the launcher surfaces guided setup instructions instead of failing cryptically.
- Tests: backend pytest coverage for the new API fields, path validation, and mount selection; frontend tests for the new task-form fields.

## Capabilities

### New Capabilities

- `mac-app-launcher`: Double-clickable macOS app that owns the local stack lifecycle — Docker detection, env materialization, compose bring-up/teardown, health gating, native web window, and readable failure states.

### Modified Capabilities

- `isolated-session-workspaces`: Workspace provisioning gains a full-access host-folder bind-mount mode with validation and safety rules (default stays isolated volume).
- `guided-task-creation`: The task form gains a local-folder field and a permission-mode choice with clear consequences.
- `run-command-center`: Run detail surfaces the folder access mode and project folder of the run.

## Impact

- **Affected code**: new `desktop/` launcher project; `backend/app/api/tasks.py` (new request fields + validation), `backend/app/api/common.py` (persist into `run.model_config`), `backend/app/worker/workspace_manager.py` (bind-mount mode), `backend/app/worker/orchestrator.py` (wire project_dir/mode through), `backend/tests/*`; `web/app/new/page.tsx`, `web/components/home/HomeTaskIntake.tsx`, `web/lib/task-form.ts`, `web/app/runs/[id]/page.tsx`, `web/__tests__/*`; `desktop/Sources/Windows.swift` (native folder-picker bridge without a global toolbar action).
- **Budget impact**: none — budget reservation/settlement logic is untouched.
- **Safety impact**: full-access mode intentionally weakens filesystem isolation for the chosen folder only, mirroring Codex's full-access mode; it is opt-in per task, clearly labeled, and the default is unchanged. Bind mounts are restricted to validated absolute paths with sensitive-root rejection. No provider keys reach the frontend; the launcher reads the Keychain item the backend itself created.
- **API-contract impact**: additive optional fields on `POST /api/tasks` (`project_dir`, `folder_access`); no breaking changes.
- **Migration impact**: none — new fields persist in the existing `task_runs.model_config` JSONB, no schema migration.
- **Non-goals**: Electron/Tauri rewrite, a fully self-contained (Docker-free) app, new execution engines, direct host execution without containers, Windows/Linux packaging, and any change to budget accounting.
