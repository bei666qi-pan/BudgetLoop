## ADDED Requirements

### Requirement: Persistent operator shell
The frontend SHALL present a consistent product shell across the dashboard, task creation, run monitoring, and report routes with BudgetLoop identity, route-aware navigation, API health communication, and a visible primary task action.

#### Scenario: Operator moves through the task lifecycle
- **WHEN** the operator navigates between primary routes
- **THEN** the shell remains recognizable and indicates the current product area without discarding route content

#### Scenario: API is unavailable
- **WHEN** the health check reports that the API cannot be reached
- **THEN** the shell communicates the degraded state without exposing credentials or replacing route-specific recovery controls

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
