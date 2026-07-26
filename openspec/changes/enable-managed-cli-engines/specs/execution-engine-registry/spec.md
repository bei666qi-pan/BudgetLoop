## MODIFIED Requirements

### Requirement: Versioned execution engine registry
The system SHALL expose OpenHands, Codex, Gemini CLI and OpenCode as typed, versioned execution engines with canonical repository, pinned source revision, pinned runnable distribution where applicable, reviewed Star count, license boundary, availability and supported transport.

#### Scenario: Operator inspects engines
- **WHEN** an authenticated operator loads the execution engine catalog
- **THEN** the system returns all four engines, identifies OpenHands as the compatibility default, distinguishes runtime-available state from source-downloaded and package-installed state and discloses whether managed AI inheritance or an engine-specific credential satisfies authentication

#### Scenario: Upstream source is bundled
- **WHEN** the repository source bootstrap is run
- **THEN** it downloads each canonical repository at a pinned revision under `vendor/agent-engines` and excludes non-open OpenHands enterprise content

#### Scenario: CLI distribution is bundled
- **WHEN** the local worker image is built
- **THEN** official fixed Codex and Gemini CLI distributions corresponding to the reviewed upstream line are installed and their commands are verified without runtime downloads

### Requirement: Replaceable execution adapter
The system SHALL route engine operations through a BudgetLoop-owned adapter contract without granting the engine authority over TaskRun state, budgets, approvals, workspaces, events, Handoffs or upstream gateway credentials.

#### Scenario: Team selects an engine
- **WHEN** an operator selects an available engine for a preset team or role
- **THEN** the applied snapshot and Runs record that engine and the worker invokes its adapter with the run-scoped managed AI environment while retaining all existing control-plane enforcement

#### Scenario: Engine is unavailable
- **WHEN** the selected binary, service, managed protocol, sandbox or required credential is unavailable
- **THEN** preflight fails with an actionable engine-specific error and the system does not silently fall back to another engine

#### Scenario: Existing clients omit engine
- **WHEN** a legacy task, Session or preset request omits execution-engine selection
- **THEN** the system uses the OpenHands compatibility default and preserves existing behavior

