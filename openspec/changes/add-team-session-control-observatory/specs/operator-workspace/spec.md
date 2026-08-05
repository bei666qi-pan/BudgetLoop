# operator-workspace Delta Specification

## Purpose

Extend the operator workspace to make the Agent Team observatory the primary Agent Team interface — replacing the legacy container workspace page with a three-panel observatory dashboard (desktop) or tabbed layout (mobile). Add team status and alert indicators to the container list so operators can assess team health at a glance. Preserve existing navigation, product shell, task dashboard, creation flows, and all other workspace routes unchanged.

## ADDED Requirements

### Requirement: Team observatory as primary Agent Team interface
The operator workspace SHALL replace the legacy container workspace page at `/containers/[id]` with the team observatory dashboard as the default and primary Agent Team detail view, presenting team status overview, session rail, team chat, and inspector panels in a single integrated layout.

#### Scenario: Operator opens a team from the container list
- **WHEN** the operator selects a team from the Agent Team container list
- **THEN** the team observatory dashboard renders with the top status bar, session list, team channel/chat, and inspector in a single route without navigating to a separate workspace page

#### Scenario: Desktop operator views team observatory
- **WHEN** the viewport is 1280px or wider
- **THEN** the observatory displays in a three-column CSS Grid layout: left SessionRail (w-72), center TeamChat (flex-1), right Inspector (w-80), with the top bar showing team status, phase, token/cost/time, and connection state

#### Scenario: Mobile operator views team observatory
- **WHEN** the viewport is narrower than 1280px
- **THEN** the observatory displays a three-tab layout (Members / Chat / Control) at a minimum of 390px width without horizontal overflow, and critical alerts appear in a sticky top banner visible across all tabs

#### Scenario: Operator's SSE connection drops
- **WHEN** the team SSE stream has not delivered an event for more than 10 seconds
- **THEN** the observatory displays a yellow "data may be stale" indicator, and after 30 seconds a red "disconnected" indicator, without hiding the most recently received data

#### Scenario: Legacy container workspace route is accessed
- **WHEN** the operator navigates to `/containers/[id]`
- **THEN** the team observatory is served; the old container workspace page component is retained in the codebase but is no longer reachable via routing

### Requirement: Team status in container list
The Agent Team container list SHALL display a team-level aggregated status for each container, including running/paused/blocked/stopped state, active session count, and an alert count for conditions requiring operator attention.

#### Scenario: Operator views the container list
- **WHEN** the Agent Team navigation item is activated
- **THEN** each container row shows its team status (running, paused, blocked, or stopped), the number of active sessions, and an alert count badge when applicable

#### Scenario: Container list API response includes team status
- **WHEN** the `GET /api/containers` endpoint returns container data
- **THEN** each item includes `team_status`, `active_session_count`, and `alert_count` fields derived from the container and its sessions

#### Scenario: No alerts are present
- **WHEN** a team has no blocking conditions, no overspend warnings, and no sessions requiring operator attention
- **THEN** the alert badge is absent from the container row

### Requirement: Alert indicators for blocking and overspend
The operator workspace SHALL surface alert indicators for blocking conditions and budget overspend risk at both the container list level and within the team observatory, so operators can quickly identify teams requiring intervention.

#### Scenario: Session is blocked in a team
- **WHEN** one or more sessions in a team have `blocked = true` in their latest progress signal
- **THEN** the container list row for that team displays a blocking alert indicator and the observatory top bar surfaces the blocked session count

#### Scenario: Team budget consumption exceeds warning threshold
- **WHEN** the team's aggregated token or cost consumption exceeds 70% of the total budget cap
- **THEN** the container list row and the observatory top bar display an overspend warning indicator, and the budget pressure mode is shown as CONSERVATIVE or CRITICAL

#### Scenario: Budget is exhausted
- **WHEN** the team's aggregated used budget exceeds the total budget cap
- **THEN** the observatory shows a CRITICAL pressure indicator, the top bar highlights the overspend, and the control panel presents recovery actions (increase budget and resume)

#### Scenario: Missing data does not generate false alerts
- **WHEN** a session has not yet reported progress or budget data
- **THEN** the observatory displays "未上报" (unreported) for the missing field rather than treating the absence as an alert condition

### Requirement: Team observatory shell and navigation integration
The team observatory SHALL integrate with the existing persistent operator shell and navigation system, preserving BudgetLoop identity, route-aware navigation, API health communication, and the existing task dashboard routes without replacing or obscuring them.

#### Scenario: Operator navigates from observatory to other workspace areas
- **WHEN** the operator uses the primary navigation to switch from the team observatory to the task dashboard, task creation, run monitoring, or reports
- **THEN** the shell remains consistent, the active navigation item updates, and the observatory state is preserved in-memory until the operator navigates away from Agent Team entirely

#### Scenario: Operator creates a new team from the observatory area
- **WHEN** the operator activates the "New Team" action from within the Agent Team area
- **THEN** the existing container creation route is loaded within the same Agent Team navigation context without discarding the shell

#### Scenario: API becomes unavailable while viewing observatory
- **WHEN** the health check reports that the API cannot be reached while the team observatory is active
- **THEN** the shell communicates the degraded state without exposing credentials, and the observatory retains the last known team data with a stale-data indicator

## MODIFIED Requirements

### Requirement: Persistent operator shell
The frontend SHALL present a consistent product shell across the task dashboard, task creation, Agent Team containers, team observatory, run monitoring, and report routes with BudgetLoop identity, route-aware navigation, API health communication, and one visible context-appropriate primary action.

#### Scenario: Operator moves through the task lifecycle
- **WHEN** the operator navigates between primary routes
- **THEN** the shell remains recognizable and indicates the current product area without discarding route content

#### Scenario: Operator moves through the Agent Team lifecycle
- **WHEN** the operator navigates between container list, container creation and team observatory routes
- **THEN** the shell identifies Agent Team as the active area and keeps team-level and session-level actions within the observatory page hierarchy

#### Scenario: API is unavailable
- **WHEN** the health check reports that the API cannot be reached
- **THEN** the shell communicates the degraded state without exposing credentials or replacing route-specific recovery controls

### Requirement: Agent Team entry point
The operator workspace SHALL provide a clear entry point to the Agent Team area — starting with a container list that shows team status, session counts, and alert indicators — without replacing or obscuring the existing task dashboard, and SHALL lead into the team observatory as the primary detail interface for each team.

#### Scenario: Operator opens Agent Team
- **WHEN** the Agent Team navigation item is activated
- **THEN** the interface shows a container list with each team's aggregated status (running/paused/blocked/stopped), active session count, alert indicators for blocking and overspend conditions, and a create-container action; selecting a team navigates to the team observatory
