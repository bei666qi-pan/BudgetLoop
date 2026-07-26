## Why

The local macOS launcher can attach to a healthy but stale Compose stack, so a
new build may leave the operator looking at an older web UI.  The repository
also has no Windows client or repeatable Windows release artifact, making a
Windows GitHub release impossible to accept honestly.

## What Changes

- Make the local web image build from the official Node image by default, while
  retaining an explicit build-argument override for approved regional mirrors.
- Make the macOS launcher safely refresh the stateless application services
  before it adopts an existing healthy stack; database and other stateful
  services remain untouched.
- Add a Windows-native, Docker Desktop-backed launcher using Tauri v2 and a
  GitHub Actions workflow that builds a signed-or-unsigned Windows installer
  artifact and runs a smoke test on a Windows runner.
- Document the platform prerequisites and release/verification boundary. The
  launcher only operates a co-located checked-out BudgetLoop repository and
  never embeds or persists provider credentials.

## Capabilities

### New Capabilities

- `windows-local-launcher`: A Windows application can locate a co-located
  BudgetLoop repository, start or attach to its Docker Compose stack, health
  gate the embedded UI, and report actionable failures.

### Modified Capabilities

- `mac-app-launcher`: An adopted healthy stack is refreshed safely when its
  stateless application images are older than the checked-out sources.

## Impact

- Affected code: `web/Dockerfile`, `desktop/Sources/LauncherCore.swift`, new
  `desktop/windows/` Tauri launcher, release workflow and README.
- Dependencies: the Windows launcher uses maintained `tauri-apps/tauri`
  (Apache-2.0; 109k+ GitHub stars, active as of 2026-07-26) and the maintained
  `tauri-apps/tauri-action` release action (MIT); it requires Docker Desktop
  and WebView2 on the operator machine.
- Safety and migration: no backend API, budget accounting, sandbox policy or
  persistent database data changes.  Only `control-plane`, `worker`, and
  `web` are rebuilt/recreated; data services and existing `.env` are
  preserved. Provider keys remain in the existing server-side/local secure
  storage paths.
- Non-goals: shipping Docker Desktop, adding Windows Keychain integration,
  rebuilding every service on every startup, or publishing a release until its
  Windows build and smoke checks pass.
