# Verification record

Date: 2026-07-25

## Backend

- `.venv/bin/pytest -q`: 517 passed, 55 skipped, 79.21% coverage.
- The 55 skipped cases are PostgreSQL integration cases whose testcontainers could
  not start because the local Docker daemon is unavailable. They cover the API,
  budget manager, observations and preset work-container transaction paths; the
  skip is environmental rather than an assertion failure.
- Focused engine, orchestrator and local CLI-worker tests passed, including a real
  bounded subprocess smoke test with a fake local `codex` executable.
- `.venv/bin/mypy app/execution_engines app/worker/orchestrator.py app/worker/cli_client.py app/worker/local_workspace.py`: passed.
- Scoped Ruff checks for the engine registry, adapters, Worker lifecycle and their tests: passed.

## Frontend

- `npm test -- --run`: 6 files and 135 tests passed.
- `npm run build`: production build passed; `/containers/new` first-load JS is 120 kB.

## Browser and design review

- Desktop and 390 × 844 mobile flows verified in the in-app Browser.
- Smart recommendation selected the game-development team for a mobile puzzle-game goal.
- Preset browsing, engine selection, role editing and start-now/create-later action states were verified.
- At 390 px, document scroll width equaled viewport width; the sticky budget/action region remained reachable.
- Browser console contained no errors.
- With the real local Codex binary and engine-scoped credentials configured, Codex
  displayed “运行时可用”; its reason reported that the command, isolated credentials
  and Worker lifecycle adapter were ready, and both creation actions were enabled.
- Gemini CLI and OpenCode truthfully remained “源码已内置 · 运行待启用” because
  their local binary/sandbox requirements were not satisfied; no engine silently
  fell back to another runtime.
- Mode 1 design review led to two targeted corrections: Chinese beginner-readable engine status copy and a mobile “仅创建” label.
- Final captures and the ten-point fidelity ledger are stored in `concepts/`.

## Execution-engine lifecycle

- The Worker now routes through the selected engine adapter. OpenHands retains its
  Docker/Agent Server path, while Codex, Gemini CLI and OpenCode use isolated local
  workspaces, optional git worktrees, bounded subprocesses, normalized public events,
  usage settlement, pause/cancel/close handling and persisted native session recovery.
- Runtime preflight requires the explicit feature flag, installed command,
  engine-scoped credentials and the engine's sandbox condition. Unsupported or
  incomplete setups fail closed without changing the user's selected engine.
