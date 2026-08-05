## ADDED Requirements

### Requirement: Fail-closed local checkout discovery
The macOS launcher SHALL start Docker-backed application services only from a standardized, validated BudgetLoop checkout selected from an explicit override or a bounded documented candidate list. It SHALL NOT use `/`, the user's home directory itself, a sensitive system directory, or an unvalidated fallback when no checkout is found.

#### Scenario: Installed application finds the desktop checkout
- **WHEN** `BudgetLoop.app` is launched from `/Applications` and a valid checkout exists at the documented `~/Desktop/BudgetLoop` candidate
- **THEN** the launcher selects that checkout and proceeds without treating `/Applications` or `/` as the repository

#### Scenario: No valid checkout can be found
- **WHEN** none of the explicit, bundle-adjacent, or bounded user candidates contains the required BudgetLoop project markers
- **THEN** the launcher performs no Compose mutation and presents a readable failure naming the attempted locations and the explicit override remedy

#### Scenario: Explicit checkout override is invalid
- **WHEN** `BUDGETLOOP_REPO` names a missing, sensitive, or unvalidated directory
- **THEN** the launcher fails closed and does not silently select a different directory

### Requirement: Recoverable native web navigation
The macOS launcher SHALL present the BudgetLoop Web UI from a trusted loopback origin only after main-frame navigation succeeds. It SHALL visibly report loading, retry transient loopback navigation failures within a bounded policy, and replace a persistent blank or failed navigation with a readable retryable failure state.

#### Scenario: First loopback navigation is transiently unavailable
- **WHEN** WebKit cannot complete the first main-frame request while the refreshed Web service is stabilizing
- **THEN** the native window keeps a visible loading state and retries within the bounded policy without requiring the operator to relaunch the app

#### Scenario: Native web navigation succeeds
- **WHEN** the trusted loopback page finishes main-frame navigation
- **THEN** the loading treatment is removed and the interactive BudgetLoop UI, including the native folder bridge, is available

#### Scenario: Native web navigation remains unavailable
- **WHEN** navigation does not succeed before retry and watchdog limits are exhausted
- **THEN** the native window shows a sanitized failure, a retry action, and an exit action instead of an empty white page

#### Scenario: Untrusted page attempts the native bridge
- **WHEN** a page outside `localhost` or `127.0.0.1` on port 3000 sends a native folder or gateway-settings message
- **THEN** the launcher rejects the message and grants no native capability

### Requirement: Explicit project gateway configuration precedence
The macOS launcher SHALL let a validated checkout explicitly opt into its
persisted, ignored `.env` gateway configuration using the exact non-secret line
`BUDGETLOOP_USE_PROJECT_AI_GATEWAY=true`. When this mode is enabled, it SHALL
NOT inject legacy Application Support or Keychain gateway values into the
Compose child process, and SHALL NOT expose project configuration to WebKit.

#### Scenario: Project gateway marker is enabled
- **WHEN** a validated checkout `.env` contains the exact project gateway marker
- **THEN** the launcher starts or refreshes gateway consumers using Compose's
  project configuration without reading a Keychain overlay

#### Scenario: Marker is absent or malformed
- **WHEN** the marker is absent, commented out, or has a different value
- **THEN** the launcher retains the existing local-settings and Keychain
  bootstrap behavior

#### Scenario: Native settings form saves project configuration
- **WHEN** a trusted loopback page submits valid gateway settings through the
  native bridge
- **THEN** the launcher persists the redacted settings and supplied key only in
  the checkout `.env` with owner-only permissions, returns no key to WebKit,
  and recreates gateway consumers without a Keychain overlay
