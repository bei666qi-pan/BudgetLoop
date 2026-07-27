# managed-cli-engine-runtime Specification

## Purpose

Define pinned CLI engine distributions, inherited AI access, isolated runtime state and readiness checks for managed Codex and Gemini CLI execution.

## Requirements

### Requirement: Pinned official CLI engine distributions
The local worker image SHALL contain exact version-pinned official Codex and Gemini CLI distributions derived from the canonical high-Star upstream projects and SHALL verify their commands during image build.

#### Scenario: Worker image is built
- **WHEN** the backend worker image is built from the checked-in Dockerfile
- **THEN** `codex` and `gemini` resolve inside the image, report the documented pinned versions and require no runtime package download

#### Scenario: Package provenance is inspected
- **WHEN** an operator audits the engine manifest and image build
- **THEN** each package maps to its canonical vendored source revision, declared license and fixed release version without a floating `latest` dependency

### Requirement: Managed AI inheritance for CLI engines
BudgetLoop SHALL allow Codex and Gemini CLI runs to use the configured gateway through a short-lived run/model-scoped runtime capability without a separate upstream API key or durable engine login when managed AI inheritance is enabled.

#### Scenario: Managed Codex run starts
- **WHEN** a live run selects Codex and inherited AI is enabled
- **THEN** the worker starts Codex with an isolated Responses provider targeting the BudgetLoop runtime, the allowed model and only the short-lived capability credential

#### Scenario: Managed Gemini CLI run starts
- **WHEN** a live run selects Gemini CLI and inherited AI is enabled
- **THEN** the worker starts Gemini CLI with the BudgetLoop Gemini runtime origin, allowed model and only the short-lived capability credential

#### Scenario: Inheritance is disabled
- **WHEN** managed AI inheritance is disabled and no valid engine-scoped login exists
- **THEN** preflight marks the CLI engine unavailable with an actionable reason and does not start or fall back to another engine

### Requirement: Isolated CLI runtime state
Each CLI engine invocation SHALL keep configuration, session state and credentials outside the project workspace and SHALL preserve BudgetLoop authority over sandbox, approvals, TaskRun state, budgets, events and Handoffs.

#### Scenario: Engine home is inspected after a run
- **WHEN** a CLI engine run completes or fails
- **THEN** the project Git state and exported artifacts contain no runtime capability, upstream key or engine login material

#### Scenario: Engine requests unsupported authority
- **WHEN** a CLI engine attempts an operation outside its assigned workspace or sandbox policy
- **THEN** the existing BudgetLoop and engine sandbox boundaries deny or pause the operation without changing TaskRun authority

### Requirement: CLI engines remain isolated from direct host-folder access
Managed CLI engines SHALL run only in their worker-local isolated workspaces and SHALL not be selected for a full-access Agent Team.

#### Scenario: Guided setup selects direct project access
- **WHEN** an operator enables direct project access for a guided Agent Team
- **THEN** the setup selects the supported server engine and does not offer CLI engines for that mode

#### Scenario: API receives a full-access CLI request
- **WHEN** a client submits a full-access Agent Team using a CLI engine
- **THEN** the API rejects the request before creating a container, task, run, or workspace

### Requirement: Verified local engine readiness
The local deployment SHALL expose Codex and Gemini CLI as selectable only after command, managed protocol, credential-inheritance, sandbox and lifecycle checks are satisfied.

#### Scenario: All managed checks pass
- **WHEN** the worker has the pinned command and verified managed runtime/sandbox configuration
- **THEN** the execution-engine API reports `runtime_available=true` and the frontend allows explicit selection

#### Scenario: Any managed check fails
- **WHEN** a required binary, protocol route, sandbox or inherited credential path is unavailable
- **THEN** the API reports `runtime_available=false` with a sanitized actionable reason and no UI or worker path silently substitutes OpenHands
