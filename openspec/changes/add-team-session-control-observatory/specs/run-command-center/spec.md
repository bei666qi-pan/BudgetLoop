# run-command-center Delta Specification

## Purpose

Extend the run command center to be team-context-aware: surface the owning container/session identity with a breadcrumb back to the team observatory, display team-level control state and session progress signals, and adapt collaboration delivery visibility to the new message state machine and CLI checkpoint-injection semantics.

## ADDED Requirements

### Requirement: Team-level control visibility
When a run belongs to a team work container, the run page SHALL surface the team-level control state and provide operators awareness of team-wide pause, resume, and stop operations that affect the run without requiring navigation to the team observatory.

#### Scenario: Run belongs to a paused team container
- **WHEN** a run that belongs to a work container is loaded and the container is in `paused` state
- **THEN** the run page displays the team暂停 indicator, explains that new LLM calls are suspended, and provides a link to the team observatory for team-level controls

#### Scenario: Team container is active
- **WHEN** a container-owned run is loaded and the container is in `active` state
- **THEN** the run page shows the team运行中 indicator without obstructing the run's own operational summary

#### Scenario: Team stop is initiated
- **WHEN** the container receives a stop command while the run detail is open
- **THEN** the run page transitions to show the terminal context and records that the run was terminated by a team-level stop, linking to the team audit event

#### Scenario: Run has no container
- **WHEN** a standalone run (not belonging to any container) is loaded
- **THEN** no team-level control indicators are displayed and the run page behaves as before

## MODIFIED Requirements

### Requirement: Run state hierarchy
The run route SHALL prioritize run status, current phase/activity, task identity, owning work container/session when present, elapsed or completion context, and the most useful next action ahead of secondary diagnostics. When the run belongs to a team work container, the run page SHALL expose a breadcrumb back to the team observatory that identifies the container and session role without revealing other sessions' private context.

#### Scenario: Run is active
- **WHEN** a non-terminal run is loaded
- **THEN** the operator can identify what the agent is doing, whether the connection is current, and where to inspect progress without interpreting raw events first

#### Scenario: Container-owned run is active
- **WHEN** a run belongs to a work session within a team container
- **THEN** the command center exposes a breadcrumb navigation path to the team observatory (`Agent Team → <Container Name> → <Session Role>`), identifies the session role and container context, and does not reveal other sessions' private context

#### Scenario: Run is terminal
- **WHEN** the run reaches a terminal state
- **THEN** the interface stops presenting it as live, offers the final report when available, and preserves the team observatory breadcrumb for container-owned runs

### Requirement: Collaboration delivery observability
The run command center SHALL expose collaboration delivery events as attributed operational facts with their full state-machine lifecycle (queued → injected → acknowledged or failed). For CLI engine runs, the interface SHALL distinguish hot-injected delivery from checkpoint-injected delivery and SHALL NOT claim a message is acknowledged before the Agent confirms receipt.

#### Scenario: Session inbox message is delivered to a server engine
- **WHEN** queued cross-session messages are injected into an Agent iteration on a server engine
- **THEN** the event timeline records the message identifier, sender/recipient attribution, idempotency key, and delivery state (`queued` → `injected` → `acknowledged`) while private content remains available only in the owning session transcript

#### Scenario: Message is delivered to a CLI engine
- **WHEN** a queued cross-session message is pending injection into a CLI engine run
- **THEN** the event timeline displays the message as `injected` with a "等待下次执行检查点" label until the Agent confirms receipt via `send_message`, after which the state transitions to `acknowledged`

#### Scenario: Message delivery fails
- **WHEN** a message remains unacknowledged after the maximum injection attempts or the session terminates
- **THEN** the event timeline shows the message state as `failed` with a "送达失败" label and the idempotency key prevents duplicate retry presentation

#### Scenario: Duplicate message is submitted
- **WHEN** a message with a previously seen idempotency key is received
- **THEN** the event timeline does not create a duplicate entry and references the existing message delivery record

### Requirement: Budget and pressure supervision
The run route SHALL communicate used, reserved when available, remaining, and limit values for supported budgets and SHALL label normal, conservative, and critical pressure without relying on color alone. When the run belongs to a team container, the run page SHALL additionally display the team-level budget aggregation context, showing where this run's consumption fits within the team totals.

#### Scenario: Budget pressure changes
- **WHEN** the API or event stream reports a new pressure mode
- **THEN** the visible budget summary updates its label and explanatory treatment while retaining the underlying numeric values

#### Scenario: Budget data is partial
- **WHEN** one or more optional budget values are absent
- **THEN** the interface labels the unavailable values with "未上报" and does not replace them with fabricated zeroes

#### Scenario: Run belongs to a team container
- **WHEN** a container-owned run is loaded and team budget aggregation data is available
- **THEN** the run page displays the team-level budget summary (team total used/limit, run's share, team pressure mode) alongside the run's own budget context, with team data fetched from `GET /api/work-containers/{id}/usage`

#### Scenario: Team budget data is unavailable
- **WHEN** a container-owned run is loaded but the team usage endpoint returns an error or is unreachable
- **THEN** the run page shows the run's own budget data and labels the team budget section as "团队数据暂不可用" without blocking the page

### Requirement: Progressive diagnostic access
The run route SHALL retain access to the event timeline, budget breakdown, reallocations, LLM calls, session progress signals, and supporting run metadata while organizing them below or alongside the primary operational summary. Session progress signals SHALL be displayed as Agent-declared structured facts (milestone, completed items, next step, blocked status, blocker reason, evidence) and SHALL NOT be inferred from heartbeat events or tool calls.

#### Scenario: Operator inspects detailed activity
- **WHEN** the operator selects a diagnostic area
- **THEN** the relevant real API data is displayed with readable labels, overflow-safe layouts, and clear empty states

#### Scenario: Operator inspects session progress signals
- **WHEN** the operator selects the progress diagnostic area for a container-owned run
- **THEN** the most recent `session_progress_signals` record for the run is displayed with its milestone, completed items, next step, blocked status with blocker reason when applicable, `needs_operator` flag, and evidence, sourced from the `session_progress_signals` table

#### Scenario: No progress signals have been declared
- **WHEN** the operator selects the progress diagnostic area but the Agent has not yet declared any progress signals
- **THEN** the interface displays "Agent 未声明进度" as an explicit empty state and does not fabricate progress from execution events or tool calls

#### Scenario: Progress signal includes a blocking condition
- **WHEN** the most recent progress signal has `blocked = true`
- **THEN** the blocker reason is displayed prominently alongside the `needs_operator` flag when true, and the run page surfaces this as a team-blocking indicator

### Requirement: Resilient live updates
The run route SHALL distinguish initial loading, live streaming or refresh, connection degradation, API error, and stale or partial data without inventing progress. When the run belongs to a team container and the team SSE event stream is the source of live updates, the run page SHALL track the team stream connection independently and surface stale-data warnings that reflect both the run-level and team-level connection state.

#### Scenario: Live connection is disrupted
- **WHEN** the event connection cannot deliver new data
- **THEN** the existing known run data remains visible and the operator receives a clear connection/retry indication

#### Scenario: Team SSE stream disconnects for a container-owned run
- **WHEN** the team SSE event stream (`GET /api/work-containers/{id}/stream`) is disconnected for more than 10 seconds while a container-owned run detail is open
- **THEN** the run page displays a "数据可能过期" warning without hiding existing data, and automatically reconnects via EventSource with `Last-Event-ID` replay

#### Scenario: Team SSE stream is disconnected for more than 30 seconds
- **WHEN** the team SSE stream has been disconnected for more than 30 seconds
- **THEN** the run page shows an "已断开" indicator and falls back to poll-based refresh at the run-level endpoint to maintain basic visibility

#### Scenario: Team SSE recovers after disconnection
- **WHEN** the team SSE stream reconnects after a disconnection
- **THEN** the run page replays missed events using `Last-Event-ID`, clears the stale-data warning, and seamlessly resumes live display
