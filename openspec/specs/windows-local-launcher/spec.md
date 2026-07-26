# Windows Local Launcher Specification

## Purpose

Provide a native Windows host for a local, Docker-backed BudgetLoop checkout.

## Requirements

### Requirement: Versioned, branded Windows MSI
The Windows launcher build SHALL embed the release version and BudgetLoop icon in its Tauri MSI and SHALL attach that MSI only to the corresponding GitHub release tag after its Windows build gate passes.

#### Scenario: Operator inspects the Windows installer
- **WHEN** an operator downloads or installs the Windows MSI from a GitHub Release
- **THEN** Windows identifies it as BudgetLoop with the BudgetLoop icon and the installer version matches the release tag

### Requirement: Windows Docker-backed local launch
The project SHALL provide a native Windows launcher that resolves a valid
co-located or operator-selected BudgetLoop repository, invokes Docker Compose
to build and start only the stateless application services, waits for the
existing local health endpoints, and then presents `http://localhost:3000` in
its native WebView2 window.

#### Scenario: Windows operator selects a valid repository
- **WHEN** the Windows launcher has a folder containing `docker-compose.yml`
  and Docker Desktop is available
- **THEN** it preserves the repository's existing `.env` and data services,
  refreshes `control-plane`, `worker`, and `web`, and navigates to the healthy
  local application URL

#### Scenario: Repository or Docker prerequisite is absent
- **WHEN** no valid repository can be resolved or Docker Desktop is not ready
- **THEN** the launcher keeps its status page visible and states the missing
  prerequisite with an actionable remedy without opening a remote endpoint

### Requirement: Repeatable Windows release artifact
The repository SHALL define a GitHub Actions Windows build that runs the
Windows launcher tests, creates an MSI installer artifact, and retains that
artifact for inspection before it is attached to a GitHub release.

#### Scenario: Windows workflow succeeds
- **WHEN** the Windows release workflow runs on `windows-latest`
- **THEN** it executes the launcher tests and uploads the generated MSI with
  its commit/version metadata as a workflow artifact

#### Scenario: Windows workflow fails
- **WHEN** the launcher tests or MSI build fails
- **THEN** no GitHub release asset is published and the failing workflow is
  the visible delivery gate
