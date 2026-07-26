# Design: mac-launcher-folder-access

## Context

Two approved workstreams share one change:

**A. macOS launcher app.** Bring-up today is manual: write `.env`, `docker compose up`, and — for the default new-api gateway — click through the new-api console to create a channel + token before anything can run (`docs/demo-guide.md`). Required services for a real run: `postgres`, `valkey`, `new-api` (default gateway), `control-plane`, `worker`, `web`; the worker mounts the host docker socket and spawns sibling workspace containers from `AGENT_SERVER_IMAGE` (`ghcr.io/openhands/agent-server:latest-python`). This machine also has a working *compatible* gateway saved in `~/Library/Application Support/BudgetLoop/ai-gateway.json` (Sangfor endpoint, model `deepseek-v4-pro-202606`) with its API key in the macOS Keychain (service constant in `backend/app/ai_gateway/local_settings.py`), which `resolve_gateway_config()` prefers over env vars on bare-metal runs. `swiftc` 6.3.3 is available, so a native shell can be built without Xcode.

**B. Codex-style folder access modes.** Today `WorkspaceManager.provision()` (`backend/app/worker/workspace_manager.py:65-120`) mounts only a named volume at `/workspace`; agent edits never touch the host. `task.workdir` is ambiguous (unused on the OpenHands transport). `CreateTaskRequest` (`backend/app/api/tasks.py:39-47`) has no folder/mode fields, but `run.model_config.project_dir` already exists as an unvalidated channel on re-runs — so persistence needs no schema migration. The risk/approval system (`backend/app/worker/risk.py` + `require_approval`) is the existing analog of codex's `AskForApproval` and stays as-is.

Per the standing convention in `AGENTS.md`, the permission model is **derived from OpenAI Codex** (vendored at `vendor/agent-engines/codex`, pinned; upstream https://github.com/openai/codex), specifically: `SandboxMode` enum (`codex-rs/protocol/src/config_types.rs:86-96`), `FileSystemSandboxPolicy::workspace_write` (`codex-rs/protocol/src/permissions.rs:570-621`), the `--add-dir`/`writable_roots` mechanism, and the policy/enforcer separation (`codex-rs/sandboxing/src/manager.rs`).

## Goals / Non-Goals

**Goals:**
- Double-clickable `BudgetLoop.app`: Docker detection/auto-start, `.env` materialization, compose bring-up + health gating, native WKWebView window, graceful teardown of app-started services, readable failure states.
- Task-level folder permission modes mirroring codex semantics: `isolated` default (codex `workspace-write` analog — writes confined to the container workspace) and `full_access` opt-in (codex `danger-full-access` + `--add-dir` analog — host folder bind-mounted rw, loud labeling), visible end-to-end from task form to run detail.
- Launcher bootstraps the gateway from the user's existing local settings + Keychain, automating the documented manual step for the compatible-gateway setup.
- End-to-end proof on this machine: real task edits a real test folder, token metering visible in the observatory panel.

**Non-Goals:**
- No Docker-free/self-contained packaging, no Electron/Tauri, no Windows/Linux app.
- No new sandbox enforcement layer (seatbelt/bwrap) inside containers — codex's own `ExternalSandbox` policy treats a known container boundary as sufficient; we follow that.
- No `.git` write carve-out inside full-access mounts (see D4 for the deliberate divergence), no network-off mode, no changes to budget accounting, no git commits.

## Decisions

### D1: Permission model = codex `SandboxMode` translated to container arguments
We adopt codex's two-user-facing-modes shape rather than inventing one:

| BudgetLoop `folder_access` | Codex analog | Enforcement (our enforcer = Docker, codex's = seatbelt/bwrap) |
|---|---|---|
| `isolated` (default) | `workspace-write` (cwd-only writes) | Only the per-run named volume is mounted at `/workspace` (rw). Zero host paths writable. Exactly today's behavior. |
| `full_access` | `danger-full-access` scoped by `--add-dir` | The validated host `project_dir` is bind-mounted rw at `/workspace` **instead of** the named volume. The container remains the only boundary (codex `ExternalSandbox` semantics: "already in an external sandbox — full disk, honor network"). |

Like codex, the *policy* is one declarative value (`folder_access` + `project_dir`, persisted in `run.model_config`) and the *enforcer* is a single translation point: `WorkspaceManager.provision()` maps it to `containers.run(volumes=…)` arguments. Approval UX and enforcement can't drift because only one module builds mounts. Mode naming in the UI mirrors codex's presentation: 隔离工作区 (default) vs 完全访问模式 rendered with codex-"Full Access"-style high-risk warning copy.

### D2: API & persistence — additive fields, no schema migration
`CreateTaskRequest` gains optional `project_dir: str | None` and `folder_access: Literal["isolated", "full_access"] = "isolated"`. Validation (pydantic): `full_access` requires `project_dir`; `project_dir` must be an absolute POSIX path after normalization, must not be `/`, `$HOME` itself, or a sensitive system root (`/System`, `/usr`, `/bin`, `/etc`, `/var`, `/private`, `/Applications`, `/Library` and their prefixes) — codex canonicalizes `--add-dir` roots the same way (`seatbelt.rs:172-186`). `create_run` persists both into `run.model_config` (existing JSONB). Existence/readability of the folder is verified by the launcher app (it runs on the host) and at provision time fail-closed by docker itself; the API does not stat host paths (containers can't see them). `task.workdir` semantics stay untouched (out of scope; flagged in exploration as ambiguous).

### D3: Provisioning changes in `WorkspaceManager`
`provision()` gains the policy: when `full_access`, build `volumes={project_dir: {"bind": "/workspace", "mode": "rw"}}` and skip the named volume and `_copy_fixture` (the folder *is* the project). The in-container `git init` + baseline commit runs only when `/workspace/.git` is absent, so pre-existing repos aren't re-initialized. Failure to mount → provision raises (fail-closed, codex's proxy fail-closed rule, `seatbelt.rs:312-322`); the run fails with a readable error instead of silently falling back to isolation. The risk module's boundary (`workdir="/workspace"`) is unchanged because the mount point is identical in both modes. Orchestrator wiring: `_ensure_workspace` reads `model_config["folder_access"]`/`["project_dir"]` and passes them through; `attach()`/checkpoints/diffs are mode-agnostic (they address the container, not the mount source).

### D4: Deliberate divergences from codex (documented, with rationale)
- **No `.git` read-only carve-out**: codex protects `.git`/`.codex`/`.agents` from agent writes to stop hook/config self-escalation on the host (`permissions.rs:22-31`). BudgetLoop's checkpointing requires git commits *inside* the workspace, and the container boundary (not file ACLs) is our escalation barrier — a rw `.git` inside the mounted folder cannot reach host credentials. Divergence accepted; UI copy tells the user the whole folder including `.git` is writable in full-access.
- **No network-off default**: codex defaults network off; our agent must reach the LLM gateway from the sibling container, so network stays at Docker default. Scoped LLM access is already handled by the managed-runtime capability tokens.
- **No seatbelt inside the container**: codex itself ships `ExternalSandbox` for exactly this case; double-sandboxing is explicitly out of scope.

### D5: Launcher app — Swift shell + lifecycle manager in `desktop/`
A single-file Swift (AppKit + WebKit) executable compiled by `desktop/build.sh` with the system `swiftc` into `BudgetLoop.app` (hand-written `Info.plist`, `desktop/Resources` icon if available, unsigned — launched locally so Gatekeeper quarantine never applies). Architecture: `LauncherCore` (state machine: `checkingDocker → startingDocker → composingEnv → startingStack → waitingHealth → ready(window) | failed(step, message, remedy)`), a status window showing progress with readable Chinese error copy, then a `WKWebView` window on `http://localhost:<WEB_PORT>`.

Lifecycle rules:
- **Docker**: `docker info` probe; if down, `open -a Docker` and poll up to 120s; if the CLI is missing entirely, fail with an "install Docker Desktop" page.
- **Env materialization**: if repo `.env` is absent, generate it from `.env.example` with random `NEW_API_SESSION_SECRET`/`POSTGRES_PASSWORD`/`MINIO_SECRET_KEY`/`API_TOKEN`; then, if `~/Library/Application Support/BudgetLoop/ai-gateway.json` exists and its Keychain secret reads non-empty, inject `AI_GATEWAY_TYPE/BASE_URL/API_KEY/RECOMMENDATION_MODEL/DEFAULT_MODEL` from it (compatible gateway) — else leave the file's gateway fields for manual setup and surface a guided-setup pane (deep-link to the new-api console) instead of failing.
- **Stack**: `docker compose up -d postgres valkey new-api control-plane worker web` in the repo (builds as needed; agent-server image pull is kicked off in parallel). If port probes show an already-healthy control-plane and web (e.g. a dev stack), the app **attaches** (adopt mode) and does not stop those services on exit; only services the app itself transitioned from down→up are stopped (`docker compose stop`) when the window closes.
- **Health gating**: poll `:8000/api/health`, `:3001/api/status`, `:3000` until ready (timeout → failure pane with `docker compose logs` tail).
- **Folder picker optimization**: an `NSOpenPanel` directory picker is invoked by a contextual “选择文件夹” action placed directly beside the 项目文件夹 field in each task-creation surface. On the conversational home surface the same action is also available in the initial goal composer's action bar, before AI planning, so operators can establish project context at the natural starting point. Following the compact composer patterns used by coding assistants such as Codex, Claude, and Gemini, the initial control is a concise folder action rather than a persistent explanatory block; after selection it shows the folder name, while the full path remains available in the review. The web action calls a `WKScriptMessageHandler` bridge, which opens the native picker and injects the chosen path back into the active form. A folder selected before planning remains operator-owned state across draft generation; AI planning cannot add, replace, or clear it. The launcher does not expose a global toolbar picker because that separates the action from the field it changes and leaves its destination ambiguous. The selected path is shown only as a read-only selection summary, not a free-text input: folder authorization must originate from the system picker, matching the Codex interaction model. A normal browser cannot safely recover the selected directory's host absolute path, so without the native bridge the UI shows a short, on-demand explanation that folder selection requires the BudgetLoop macOS App instead of accepting an unverifiable manually typed path.

### D6: End-to-end acceptance on this machine
Create `/Users/qi/budgetloop-e2e/` (tiny project: one buggy Python function + one failing test), build the app, launch it (real double-click equivalent: `open BudgetLoop.app`), create a task via the UI/API with `folder_access=full_access, project_dir=/Users/qi/budgetloop-e2e` and a small budget, let the worker run it to terminal with the Sangfor gateway, then verify: (1) the bug is fixed in the host folder on disk (`git diff`/file content), (2) `GET /api/runs/{id}/llm-calls` returns real calls, (3) headless-browser screenshot of the run's 观测 tab shows the metering. If the gateway key/endpoint or the agent-server image proves unreachable, stop and report — no mocked acceptance.

## Risks / Trade-offs

- [Full-access mode exposes a real host folder to agent mistakes] → opt-in per task, sensitive-root rejection, codex-style loud warning copy, container still the boundary, and the run page permanently shows the mode.
- [Compose env drift between the user's hand-rolled `.env` and launcher expectations] → launcher only *fills missing* values, never overwrites an existing `.env`; adopt-mode avoids fighting a running stack.
- [ghcr.io agent-server image pull may fail on this network] → pre-pull with mirror fallback during e2e; stop rule reports honestly if unobtainable.
- [Keychain read from the unsigned launcher may prompt the user once] → acceptable one-time OS prompt; documented in the failure pane if denied (falls back to guided gateway setup).
- [Sibling containers on the default bridge can't resolve compose DNS (`new-api`)] → the compatible gateway is an external URL so it resolves everywhere; for new-api-based setups the managed-runtime already routes in-workspace LLM calls via `host.docker.internal`, and this limitation is noted for the guided path.
- [Enterprise aTrust routes may resolve only on macOS] → for an explicitly configured Sangfor-compatible endpoint, the launcher may detect the user's already-running loopback-only compatible relay and pass its Docker Desktop host address to the compose process for that launch only. The original URL and Keychain secret are not changed or persisted; absent a healthy relay, normal direct configuration remains unchanged. When it adopts an existing stack that lacks this temporary configuration (or is still unhealthy on the prior direct route), it recreates only the stateless control-plane and worker services, never the data services and never marks the adopted stack for teardown. The health probe uses a deliberately invalid empty Chat Completions request when a compatible gateway does not expose `/models`, so it never requests model output.
- [Transient package-index reads during local Docker rebuild] → the backend image uses BuildKit's standard pip cache mount plus pip retry/timeout options. This contains no proxy or credential configuration and only improves installation resilience for the launcher-managed local build.
- [Scope creep from "相应优化"] → launcher optimizations limited to: adopt/attach, parallel image pre-pull, progress/error readability, and the contextual folder-picker bridge. Nothing else.

## Migration Plan

Additive only. Ships in four verifiable steps: (1) backend fields + provisioning + pytest, (2) frontend form + run detail + vitest, (3) `desktop/` launcher + build script + manual launch test, (4) e2e acceptance. Rollback = revert; existing runs/volumes/containers are unaffected because default behavior is byte-identical.

## Open Questions

None blocking. (Resolved during exploration: `workdir` ambiguity deferred; `.git` carve-out rejected; gateway bootstrap prefers compatible local settings over new-api automation.)
