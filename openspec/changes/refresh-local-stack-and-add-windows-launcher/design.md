## Context

The current macOS launcher considers a responding web/control-plane stack
ready, even if its images were built before the checked-out sources changed.
This violates the operator expectation that reopening the desktop application
uses the version they just built.  The web Dockerfile also defaults to a
regional mirror that is not reliable in the current environment.

The existing desktop client is Swift/AppKit/WebKit and therefore cannot build
for Windows.  A Windows distribution must launch the same Compose services,
not duplicate the control plane or weaken its credential/sandbox boundaries.

## Goals / Non-Goals

**Goals:**

- Ensure every local desktop start uses a freshly built stateless application
  image, without altering PostgreSQL, Valkey, New API, volumes, or `.env`.
- Provide a maintained, native Windows launcher with clear Docker/repository
  diagnostics and an embedded BudgetLoop UI after health gates pass.
- Produce a repeatable Windows installer artifact in GitHub Actions and test
  its Rust launcher logic on a Windows runner.

**Non-Goals:**

- Do not make the launcher a standalone model runtime or package Docker
  Desktop, repository sources, databases, or provider credentials.
- Do not change control-plane APIs, budgets, workspace sandbox semantics, or
  native macOS Keychain behavior.
- Do not auto-publish an unverified GitHub release.

## Decisions

### Rebuild only stateless services at desktop startup

Both the macOS adopted-stack path and the Windows launcher run
`docker compose up -d --build control-plane worker web`. Docker layer caching
makes an unchanged source start inexpensive; when a source changed it is
guaranteed to replace the stale application image. Compose dependencies remain
healthy and data services are never passed to a force-recreate or build
command. The launch UI explicitly communicates the refresh phase and retains
the existing bounded failure output/redaction.

Alternative: compare image timestamps with source mtimes. Rejected because
checkouts, restores, and untracked source files make timestamp comparisons
unreliable. Alternative: rebuild the entire stack. Rejected because it adds
avoidable disruption to stateful services.

### Use the official Node image as the portable default

`web/Dockerfile` defaults to `node:20-alpine`, which is the image name Docker
can cache and resolve through the operator's configured registry. The existing
`NODE_IMAGE` build argument remains available for an explicitly configured,
approved mirror. This keeps the image source and digest policy under Docker's
normal configuration rather than hard-coding a single third-party mirror.

### Add a small Tauri v2 Windows host, not a second application stack

The Windows host uses the maintained Tauri v2 framework (Tauri repository:
109k+ GitHub stars, active 2026-07-26, Apache-2.0) to create a native WebView2
window. It resolves a repository from an explicit environment variable, its
saved local selection, or an operator-selected folder; then invokes Docker
Compose, waits for the existing localhost health endpoints, and navigates only
to `http://localhost:3000`. The only persisted setting is a local repository
path; no key, token, or server secret enters the Tauri configuration or UI.

Alternative: Electron. Rejected because it introduces a much larger runtime
for a launcher and offers no advantage for this local URL host. Alternative:
a PowerShell-only zip. Rejected because it cannot provide the required native
window and tends to be blocked by Windows execution policy.

### Build, test, and expose Windows artifacts through GitHub Actions

The workflow runs `cargo test` and `cargo tauri build --bundles msi` on
`windows-latest`, uploads the MSI as a workflow artifact, and publishes it
only when a manually-created GitHub release tag is supplied. The maintained
`tauri-apps/tauri-action` is used for the release upload step. Hosted Windows
runners do not provide Docker Desktop's Linux engine, so Compose bring-up is
not claimed as CI acceptance; the launcher unit tests cover repository
resolution and command construction, while a full launch requires a real
Windows machine with Docker Desktop.

## Risks / Trade-offs

- [Image rebuild takes longer on a cold cache] → Status UI names the refresh
  phase and the cache avoids repeated package installation for unchanged code.
- [Docker Desktop or WebView2 is absent on Windows] → The host presents an
  actionable prerequisite error before opening the web UI.
- [A selected folder is not a BudgetLoop checkout] → Validate that it contains
  `docker-compose.yml` before persisting it or invoking Docker.
- [Windows artifact compiles but a specific device has Docker issues] → The
  release documents the required Docker Desktop check and the launcher keeps
  failures visible instead of falling back to a stale or remote instance.

## Migration Plan

1. Build the refreshed images locally and verify the new Agent Team controls
   in the actual desktop URL.
2. Ship the launcher changes as additive files; existing macOS invocation and
   Compose commands remain compatible.
3. Run macOS build checks and Windows GitHub Actions build/tests; inspect the
   produced MSI artifact before making a release.
4. Roll back by using the previous launcher binary; no schema, volume, or
   environment migration is needed.

## Open Questions

- A full Docker-backed Windows launch needs a real Windows Docker Desktop
  machine after the CI artifact is available; the hosted runner cannot supply
  that daemon.
