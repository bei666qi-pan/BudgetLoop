## MODIFIED Requirements

### Requirement: Persistent operator shell
The frontend SHALL present a consistent product shell across the task dashboard, task creation, Agent Team containers, run monitoring, and report routes with BudgetLoop identity, route-aware navigation, API health communication, and one visible context-appropriate primary action.

#### Scenario: Operator moves through the task lifecycle
- **WHEN** the operator navigates between primary task routes
- **THEN** the shell remains recognizable and indicates the current product area without discarding route content

#### Scenario: Operator moves through the Agent Team lifecycle
- **WHEN** the operator navigates between container list, container creation and container detail routes
- **THEN** the shell identifies Agent Team as the active area and keeps container/session actions within the page hierarchy

#### Scenario: API is unavailable
- **WHEN** the health check reports that the API cannot be reached
- **THEN** the shell communicates the degraded state without exposing credentials or replacing route-specific recovery controls

## ADDED Requirements

### Requirement: Agent Team entry point
The operator workspace SHALL provide a clear entry point to work containers without replacing or obscuring the existing task dashboard.

#### Scenario: Operator opens Agent Team
- **WHEN** the Agent Team navigation item is activated
- **THEN** the interface shows container summaries, session counts, live/attention state and a create-container action
