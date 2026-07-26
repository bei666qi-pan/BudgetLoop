# operator-workspace Specification

## Purpose

Define the persistent product shell and actionable task workspace used throughout the operator lifecycle.
## Requirements
### Requirement: Persistent operator shell
The frontend SHALL present a consistent product shell across the task dashboard, task creation, Agent Team containers, run monitoring, and report routes with BudgetLoop identity, route-aware navigation, API health communication, and one visible context-appropriate primary action.

#### Scenario: Operator moves through the task lifecycle
- **WHEN** the operator navigates between primary routes
- **THEN** the shell remains recognizable and indicates the current product area without discarding route content

#### Scenario: Operator moves through the Agent Team lifecycle
- **WHEN** the operator navigates between container list, container creation and container detail routes
- **THEN** the shell identifies Agent Team as the active area and keeps container/session actions within the page hierarchy

#### Scenario: API is unavailable
- **WHEN** the health check reports that the API cannot be reached
- **THEN** the shell communicates the degraded state without exposing credentials or replacing route-specific recovery controls

### Requirement: Agent Team entry point
The operator workspace SHALL provide a clear entry point to work containers without replacing or obscuring the existing task dashboard.

#### Scenario: Operator opens Agent Team
- **WHEN** the Agent Team navigation item is activated
- **THEN** the interface shows container summaries, session counts, live/attention state and a create-container action

### Requirement: Actionable task dashboard
The dashboard SHALL prioritize task discovery and continuation by showing each task's identity, latest run status, meaningful resource summary when available, and a direct action to inspect or start work.

#### Scenario: Tasks are available
- **WHEN** the task list API returns one or more tasks
- **THEN** the operator can distinguish active, completed, failed, budget-exhausted, and not-yet-run work and open the appropriate run

#### Scenario: No tasks exist
- **WHEN** the task list API returns an empty collection
- **THEN** the dashboard explains the empty state and presents a direct create-task action

### Requirement: Local task discovery controls
The dashboard SHALL provide client-side search and status filtering over the task data returned by the API and SHALL clearly distinguish an empty filter result from an empty account.

#### Scenario: Search matches task content
- **WHEN** the operator enters a query matching a task name or identifier
- **THEN** only matching returned tasks are shown and the query can be cleared

#### Scenario: Filters have no matches
- **WHEN** active filters exclude all returned tasks
- **THEN** the dashboard shows a no-results state with a way to reset the filters

### Requirement: Resilient dashboard states
The dashboard SHALL expose loading, retryable error, partial-data, and refresh behavior without fabricating task or run state.

#### Scenario: Task request fails
- **WHEN** the task list request returns an error
- **THEN** the dashboard shows a trustworthy error message and a retry action while retaining the application shell

### Requirement: Beginner-first Agent Team creation
The operator workspace SHALL make AI-assisted smart recommendation and ready-to-use presets the primary Agent Team creation path while preserving deterministic local recommendation and an advanced manual path, and SHALL explain the active recommendation source without exposing gateway secrets.

#### Scenario: First-time operator describes a goal
- **WHEN** the operator enters a meaningful project goal
- **THEN** the interface can load a ranked recommendation, explain why it matches and present a complete editable team preview without asking for framework or provider configuration

#### Scenario: AI recommendation is ready
- **WHEN** the gateway status reports a healthy configured recommendation model
- **THEN** the interface states that AI-assisted recommendation is available, identifies the audited gateway and explains that submitted recommendation fields may be sent to it

#### Scenario: Local recommendation is active
- **WHEN** AI is disabled, unconfigured or a recommendation request falls back
- **THEN** the interface remains usable, labels the result as local deterministic matching and presents actionable gateway recovery guidance without treating fallback as a creation error

#### Scenario: Operator opens gateway administration
- **WHEN** a safe New API console URL is configured and the operator chooses gateway settings
- **THEN** the interface opens the upstream New API console separately rather than collecting provider credentials inside BudgetLoop

#### Scenario: Operator browses instead of describing
- **WHEN** the operator selects preset browsing
- **THEN** the interface provides category filters and readable open-list rows for common teams and updates one shared preview when a preset is selected

#### Scenario: Operator chooses immediate or later start
- **WHEN** the team preview is valid
- **THEN** one primary action creates and starts the team and one secondary action creates it for later, with distinct in-flight, success and error feedback

#### Scenario: Creation is viewed on mobile
- **WHEN** the route is rendered at a narrow viewport
- **THEN** gateway status, recommendation, role inspection and preset browsing remain usable without horizontal overflow and the aggregate budget plus creation action remain reachable in a mobile action region

### Requirement: Conversational home hierarchy
The operator workspace SHALL make a plain-language task composer the primary home-page action while retaining task status discovery, search, filtering, and direct continuation as a secondary recent-work region.

#### Scenario: Home page has no tasks
- **WHEN** the task API returns an empty collection
- **THEN** the home page leads with example-assisted goal entry and does not require the operator to navigate to a separate form before describing work

#### Scenario: Home page has existing tasks
- **WHEN** the task API returns one or more tasks
- **THEN** the composer remains prominent and the existing status summary, search, filters, and run actions remain reachable below it

#### Scenario: Operator prefers advanced setup
- **WHEN** the operator chooses manual task configuration, preset browsing, or empty-container creation
- **THEN** the workspace exposes the existing advanced route without discarding the home draft or mislabelling it as started

### Requirement: Attention-preserving home state
The home page SHALL keep actionable existing work visible while a new setup draft is idle, planning, ready, or in error and SHALL not let the creation surface hide tasks that require approval or recovery.

#### Scenario: Existing run needs attention
- **WHEN** a returned task has a waiting-approval, failed, or other attention status
- **THEN** the recent-work region exposes its status and direct continuation action even when a new draft is present

### Requirement: Beginner-first inherited AI runtime
The operator workspace SHALL explain that AI applications created by BudgetLoop automatically use the configured managed gateway through a scoped server-side runtime and do not require a second project API key or secret-bearing `.env` file.

#### Scenario: Operator creates an AI application
- **WHEN** a project goal describes an AI game, writing assistant or other AI-powered application
- **THEN** the interface explains that server-side generated code will inherit BudgetLoop AI access automatically while browser code will use the generated application's server route

#### Scenario: Managed gateway is unavailable
- **WHEN** the configured gateway or aTrust route is unavailable
- **THEN** the interface shows a non-secret actionable readiness state and does not claim that the generated AI application can make remote model calls

#### Scenario: Operator inspects credential behavior
- **WHEN** the operator reviews the team or runtime configuration
- **THEN** the interface states that the upstream key stays in BudgetLoop or the OS secret store and is not copied into the generated repository

#### Scenario: Operator changes inherited runtime policy
- **WHEN** the operator opens authenticated AI settings
- **THEN** the interface exposes a default-on managed-app inheritance switch and accurately previews the effect of disabling it without revealing the saved upstream key

### Requirement: Progressive conversational review hierarchy
The operator workspace SHALL keep goal, team, engine, folder access, and the primary confirmation action visible while placing implementation-oriented recommendation, topology, role-budget, gateway, and audit detail behind progressive disclosure.

#### Scenario: Beginner reviews a successful AI draft
- **WHEN** a valid AI-backed draft is ready
- **THEN** the review presents a concise ready state and primary next action without a prominent gateway or implementation-detail card

#### Scenario: Local fallback produces a usable draft
- **WHEN** AI genuinely fails and local recommendation produces a valid draft
- **THEN** the review shows a compact neutral provenance status with optional sanitized detail and does not visually treat the draft as an error

#### Scenario: Operator needs advanced detail
- **WHEN** the operator expands advanced configuration or provenance
- **THEN** role, budget, engine-readiness, approval, permission, and recommendation facts remain inspectable and editable within existing enforcement bounds

### Requirement: Recent-history deletion interaction
The recent-work region SHALL expose a secondary delete action for eligible terminal standalone tasks, require a task-specific confirmation, and preserve the row with error feedback until deletion succeeds.

#### Scenario: Operator confirms task deletion
- **WHEN** an eligible task's delete action is activated and the named confirmation is accepted
- **THEN** the interface waits for the API result and removes only that task row after success

#### Scenario: Task cannot be deleted
- **WHEN** the API rejects deletion because the task is active or team-owned
- **THEN** the row remains present and the interface explains the lifecycle or ownership restriction without exposing backend internals
