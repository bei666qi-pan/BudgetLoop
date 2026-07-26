## ADDED Requirements

### Requirement: Branded launcher waiting state
The macOS launcher SHALL display a branded, readable waiting state before the web UI is ready, including the BudgetLoop loop mark, the current safe launch status, and indeterminate progress that does not fabricate completion percentage.

#### Scenario: Local services are starting
- **WHEN** the launcher is checking Docker, preparing configuration, starting services, or waiting for health checks
- **THEN** the status window presents the mark, a plain-language current status, and visible activity feedback

#### Scenario: Reduced motion is enabled
- **WHEN** macOS requests reduced motion
- **THEN** non-essential loading transitions are reduced while status and activity remain understandable

### Requirement: Recoverable launcher failure state
The macOS launcher SHALL replace the waiting treatment with a readable failure state containing the failed step, a redacted message, a practical remedy, and an accessible exit action.

#### Scenario: Launcher startup fails
- **WHEN** the launcher reports a terminal startup failure
- **THEN** the window stops the active loading indicator and exposes failure details and the exit action without relying on color alone

### Requirement: Packaged application mark
The macOS application bundle SHALL contain a vector-derived BudgetLoop icon based on the supplied interlocking-loop mark, referenced by bundle metadata and visible to Finder/Dock shortcuts.

#### Scenario: Application is packaged
- **WHEN** `desktop/build.sh` builds the app bundle
- **THEN** the bundle contains `BudgetLoop.icns` and its Info.plist references that icon
