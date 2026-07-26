# Tasks: mac-launcher-folder-access

## 1. Backend: folder access policy

- [x] 1.1 Add `project_dir` (optional) and `folder_access` (`isolated`|`full_access`, default `isolated`) to `CreateTaskRequest` in `backend/app/api/tasks.py` with pydantic validation: absolute normalized POSIX path required for `full_access`; reject `/`, the home directory itself, and sensitive roots (`/System`, `/usr`, `/bin`, `/etc`, `/var`, `/private`, `/Applications`, `/Library`)
- [x] 1.2 Persist both fields into `run.model_config` in `backend/app/api/common.py` (`create_run`) so they survive to the worker without schema migration
- [x] 1.3 Extend `WorkspaceManager.provision()` in `backend/app/worker/workspace_manager.py`: for `full_access`, bind-mount `project_dir` rw at `/workspace` instead of the named volume, skip fixture copy, `git init` only when `.git` absent; fail closed with a readable error if the mount is rejected; wire the policy through `Orchestrator._ensure_workspace`
- [x] 1.4 Backend tests: new validation cases (absolute-path, sensitive roots, mode-without-folder) and workspace-manager mount-selection cases (mocked docker, matching `test_workspace_manager.py` style); run the related pytest subset green

## 2. Frontend: folder picker + mode selection

- [x] 2.1 Task form (`web/app/new/page.tsx` + `web/lib/task-form.ts`): optional 项目文件夹 path field + 权限模式 radio (隔离工作区 default / 完全访问模式) with codex-style high-risk warning copy for full access; inline error when full access has no folder; submit new fields in `POST /api/tasks`
- [x] 2.2 Run detail (`web/app/runs/[id]/page.tsx`): show 权限模式 badge (完全访问模式 distinctly marked) and the project folder path from `run.model_config`
- [x] 2.3 Frontend tests for form validation and run-detail mode display; `npm test` and `npm run build` green
- [x] 2.4 Put the system `选择文件夹` action in every task-creation context: beside a read-only 项目文件夹 selection summary on review/advanced surfaces and as a compact, low-copy action in the initial conversational goal composer before AI planning; preserve the operator-owned selection across draft generation, reveal a short native-picker explanation only when needed, and add focused interaction coverage

## 3. Desktop launcher app

- [x] 3.1 Create `desktop/` project: single-file Swift (AppKit + WebKit) launcher with state machine (checkingDocker → startingDocker → materializingEnv → startingStack → waitingHealth → ready | failed), status window with readable Chinese progress/error copy, `Info.plist`, and `desktop/build.sh` compiling with system `swiftc` into `BudgetLoop.app`
- [x] 3.2 Lifecycle: `docker info` probe + `open -a Docker` fallback with timeout; `.env` materialization from `.env.example` with generated secrets (never overwrite); inject local compatible-gateway settings (`~/Library/Application Support/BudgetLoop/ai-gateway.json` + Keychain via `security` CLI) as `AI_GATEWAY_*` env; guided-setup failure pane when gateway config is unavailable
- [x] 3.3 Stack management: `docker compose up -d` of required services, parallel pre-pull of the agent-server image, health gating on `:8000/api/health` + `:3001/api/status` + `:3000`, adopt-mode when a healthy stack already answers, graceful `docker compose stop` on window close only for app-started services
- [x] 3.4 `NSOpenPanel` folder picker bridge that fills the task form folder field via `WKScriptMessageHandler` (additive)
- [x] 3.5 Build `BudgetLoop.app`, launch it, verify bring-up to a working web UI window; readable failure for simulated port conflict
- [x] 3.6 Remove the global top-right folder-picker toolbar item while retaining the `WKScriptMessageHandler` → `NSOpenPanel` bridge used by contextual web controls; rebuild the app and verify the picker still fills the adjacent field

## 4. End-to-end acceptance

- [x] 4.1 Create `/Users/qi/budgetloop-e2e/` test project (one buggy Python function + one failing test)
- [x] 4.2 Launch via `open BudgetLoop.app`; through the UI or API create a task with `folder_access=full_access`, `project_dir=/Users/qi/budgetloop-e2e`, small budget; run to a terminal state with the real gateway
- [x] 4.3 Verify the bug is fixed in the host folder on disk, `GET /api/runs/{id}/llm-calls` returns real calls, and a headless-browser screenshot of the run's 观测 tab shows real metering; if the gateway credential/endpoint or agent-server image is unobtainable, stop and report honestly
- [x] 4.4 Re-run `cd web && npm test` + `npm run build` and the related backend pytest subset; all exit 0
- [x] 4.5 Verify the launcher routes an explicitly configured Sangfor-compatible gateway through an already-running local relay without persisting the relay address or exposing the Keychain secret; verify the no-output compatible-gateway health fallback for gateways without `/models`.
