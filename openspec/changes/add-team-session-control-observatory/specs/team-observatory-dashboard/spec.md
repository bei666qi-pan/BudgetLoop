# team-observatory-dashboard Specification

## Purpose

Define the team-level observatory dashboard that gives the operator a 5-second team health snapshot, a desktop three-panel layout with session list, team channel, and inspector, and a mobile tab layout without horizontal overflow at 390px — all driven by PostgreSQL as the sole source of truth.

## ADDED Requirements

### Requirement: 5-second team status overview
The dashboard top bar SHALL present the operator with a complete team health snapshot — status, phase, aggregate Token/cost/elapsed-time, connection state, and active/waiting/blocked/completed session counts — within 5 seconds of entering the container page, using data from `GET /api/work-containers/{id}` and `GET /api/work-containers/{id}/usage`.

#### Scenario: Operator enters a running team
- **WHEN** the operator navigates to a container with at least one running session
- **THEN** the top bar renders team status (active/paused/blocked), phase label, aggregate Token and cost from `usage_summary`, elapsed wall-clock time, connection indicator, running/waiting/blocked session counts, and pause/stop controls within 5 seconds

#### Scenario: Team has no active sessions
- **WHEN** the container has zero RUNNING sessions and the team is not paused
- **THEN** the top bar shows idle/completed status with zero active counts, the latest team phase, and a resume action where applicable

#### Scenario: Initial API request is slow
- **WHEN** the container GET or usage GET exceeds 5 seconds to respond
- **THEN** the top bar shows a skeleton placeholder for the affected metrics and transitions to real data once the response arrives, without blocking the rest of the dashboard paint

### Requirement: Desktop three-panel layout
At viewport widths ≥ 1280px the dashboard SHALL render a three-panel CSS Grid layout: a left SessionRail (w-72), a centre TeamChat (flex-1), and a right Inspector (w-80). The Inspector SHALL default to collapsed detail for at least one section and SHALL allow the operator to expand/collapse progress, usage, and control blocks independently.

#### Scenario: Desktop operator opens the team dashboard
- **WHEN** the viewport is ≥ 1280px wide and the container page loads
- **THEN** the layout renders three non-overlapping panels: SessionRail on the left, TeamChat in the centre, Inspector on the right, with the Inspector's progress, usage, and control sections independently collapsible

#### Scenario: Operator selects a session in the rail
- **WHEN** the operator clicks a session entry in the SessionRail
- **THEN** the centre panel switches to that session's conversation transcript and the Inspector updates to show that session's progress, usage, and individual controls while the rail highlight follows the selection

#### Scenario: Inspector is fully collapsed
- **WHEN** the operator collapses every section in the Inspector
- **THEN** the centre panel expands to fill the freed space without layout shift and a restore affordance remains visible

### Requirement: Mobile tab layout
At viewport widths < 1280px the dashboard SHALL render three tabs — 成员 (Members), 对话 (Chat), 控制 (Control) — that switch the main content region. The layout SHALL fit within 390px without horizontal overflow, and the tab bar plus top bar plus any active alert banner SHALL all be visible without scrolling.

#### Scenario: Operator on a 390px-wide device
- **WHEN** the dashboard renders at 390px viewport width
- **THEN** the three tab labels, top bar summary, and alert banner (if present) are fully visible without horizontal scroll, and each tab content area is reachable by a single tap

#### Scenario: Operator switches mobile tabs
- **WHEN** the operator taps the 对话 tab
- **THEN** the content region switches to the team channel or selected-session chat without losing the top bar status, the selected tab is visually distinct, and the other two tabs remain immediately tappable

#### Scenario: Critical alert is active while on a non-members tab
- **WHEN** a blocking or overspend alert is active and the operator is viewing the 控制 or 对话 tab
- **THEN** the alert banner remains visible at the top of the viewport above the tab bar

### Requirement: Session list with status, action, and pressure
The SessionRail (desktop) and 成员 tab (mobile) SHALL list every session in the container with at minimum: session name, run status, current public action or latest progress summary, Token consumption, and budget-pressure level (NORMAL / CONSERVATIVE / CRITICAL). The list SHALL auto-filter to the container's sessions from `GET /api/work-containers/{id}` and SHALL display dependency-waiting sessions with a distinct indicator.

#### Scenario: Sessions are in varied states
- **WHEN** the container has running, waiting, blocked, and completed sessions
- **THEN** the session list shows each with its real status icon, the running sessions show current action text, waiting sessions show their dependency target, blocked sessions show the blocker reason, and completed sessions show a terminal indicator

#### Scenario: Session hits CONSERVATIVE pressure
- **WHEN** a session's consumption reaches the CONSERVATIVE threshold as defined by the backend budget manager
- **THEN** the session list entry displays CONSERVATIVE pressure with a distinct visual treatment, the session is elevated in sort order above NORMAL sessions, and the alert banner fires if cross-tab visibility rules require it

#### Scenario: Session hits CRITICAL pressure
- **WHEN** a session's consumption reaches the CRITICAL threshold
- **THEN** the session list entry displays CRITICAL pressure, the session sorts to the top, and a cross-tab alert banner fires immediately regardless of the active tab

### Requirement: Cross-tab alert visibility for approval, blocking, and overspend
Alerts for operator-approval-required items, blocked sessions, and overspend/CRITICAL pressure SHALL render as a fixed banner above the tab bar on mobile and as a persistent inline strip on desktop. An alert SHALL remain visible regardless of which tab or panel the operator is viewing and SHALL clear only when the underlying condition resolves.

#### Scenario: Session becomes blocked on a dependency
- **WHEN** a session transitions to blocked status with a dependency reason
- **THEN** a blocking alert banner appears at the top of the dashboard on both desktop and mobile and stays visible until no blocked sessions remain

#### Scenario: Multiple alerts fire concurrently
- **WHEN** one session is blocked, another needs approval, and a third is at CRITICAL pressure
- **THEN** all three alert types are presented in the banner (or a condensed multi-alert summary on mobile), each with enough context for the operator to triage, and they persist until their respective conditions clear

#### Scenario: All alerts resolve
- **WHEN** every blocking, approval, and overspend condition clears
- **THEN** the alert banner is removed without leaving a blank reserved space that shrinks the usable viewport

### Requirement: No fake progress
The dashboard SHALL display progress only from Agent-declared structured progress signals stored in `session_progress_signals`. It SHALL NOT infer, calculate, or estimate progress from heartbeat events, LLM call counts, elapsed time, iteration numbers, or any other non-declarative source. When no progress signal exists for a session the dashboard SHALL display "Agent 未声明进度" rather than a fabricated percentage or milestone.

#### Scenario: Agent declares a milestone
- **WHEN** the Agent writes a progress signal with milestone, completed_items, and next_step to `session_progress_signals`
- **THEN** the Inspector and session list entry reflect exactly that declared milestone and completed-item count without extrapolating a percentage unless an explicit finite milestone list is also declared

#### Scenario: Agent has not declared any progress
- **WHEN** a running session has no row in `session_progress_signals`
- **THEN** the dashboard displays "Agent 未声明进度" for that session and does not fall back to iteration count, elapsed time, or any other proxy

#### Scenario: Explicit finite milestones enable a percentage
- **WHEN** the latest progress signal declares a completed_items list and an explicit finite total milestone count
- **THEN** the dashboard may display a completed/total fraction derived solely from those declared values and SHALL NOT fabricate an estimated total

### Requirement: Budget and usage display
The Inspector's usage section and the mobile 控制 tab SHALL display team-aggregate Token used/limit, estimated cost, wall-clock and active elapsed time, LLM call count, consumption rate, and projected exhaustion time. Session-level split SHALL also be available. Every metric SHALL derive from `GET /api/work-containers/{id}/usage`. Fields absent from the backend response (null `estimated_cost`, missing rate data) SHALL display "未上报" and SHALL NOT render as zero, a fabricated trend, or a hidden row.

#### Scenario: Full usage data is available
- **WHEN** the usage endpoint returns complete Token, cost, time, call-count, rate, and exhaustion data
- **THEN** every metric renders with its value and unit, the team aggregate is visibly distinct from per-session rows, and the NORMAL/CONSERVATIVE/CRITICAL pressure label matches the backend's computed pressure

#### Scenario: Cost data is absent
- **WHEN** `estimated_cost` is null for every session
- **THEN** the cost row displays "未上报" and the cost contribution to any trend or gauge is omitted

#### Scenario: Consumption rate cannot be computed
- **WHEN** fewer than two LLM calls with timestamps exist or elapsed time is near zero
- **THEN** the consumption rate and projected-exhaustion rows display "未上报" rather than a division-by-zero placeholder

### Requirement: Team and session control actions
The Inspector's control section and the mobile 控制 tab SHALL expose team-level pause/resume/stop actions, runtime budget adjustment, and max-parallel-LLM-call adjustment. When a session is selected, per-session pause/resume/cancel and budget-adjust actions SHALL also be available. All actions SHALL call the corresponding API endpoints, SHALL show the current and new value before mutation, and budget adjustments SHALL be rejected by the UI before sending if the new max is below used + reserved.

#### Scenario: Operator pauses the team
- **WHEN** the operator activates the team pause control
- **THEN** `POST /api/work-containers/{id}/pause` is called, the top bar status transitions to paused, and the pause button is replaced by a resume affordance

#### Scenario: Operator adjusts team budget upward
- **WHEN** the operator opens the budget adjustment and enters a new max that is ≥ current used + reserved
- **THEN** `PATCH /api/work-containers/{id}/budget` is called with the new value, the usage display updates, and a `needs_resume: true` response triggers a "已增加预算，请点击恢复" prompt

#### Scenario: Operator attempts budget below used + reserved
- **WHEN** the operator enters a new max lower than current used + reserved
- **THEN** the UI rejects the input before any API call and explains why the floor constraint applies

#### Scenario: Stop requires confirmation
- **WHEN** the operator activates the team stop control
- **THEN** a confirmation dialog explains that stop is irreversible and lists affected sessions; `POST /api/work-containers/{id}/stop` is only called after explicit confirmation

#### Scenario: Control action is idempotent
- **WHEN** the operator pauses an already-paused team or resumes an already-running team
- **THEN** the API returns a success response with no state change, and the dashboard reflects the unchanged state without an error flash

### Requirement: SSE connection and stale-data indicator
On desktop the dashboard SHALL connect to `GET /api/work-containers/{id}/stream` via EventSource and update session list, message feed, progress, and usage displays from incoming events without full-page polling. SHALL fall back to 3-second polling when EventSource is unavailable. A connection-state indicator SHALL show "已连接" when events arrive within 10 seconds, "数据可能过期" (amber) after 10–30 seconds of silence, and "已断开" (red) after >30 seconds of silence, with automatic retry.

#### Scenario: SSE events flow normally
- **WHEN** the EventSource connection is established and events arrive within 10-second intervals
- **THEN** the connection indicator shows green "已连接", and session-status, message, and progress changes update in the dashboard without operator refresh

#### Scenario: SSE connection drops briefly
- **WHEN** no event arrives for 15 seconds but the connection is not closed
- **THEN** the indicator switches to amber "数据可能过期", the last-known data remains visible, and the indicator reverts to green once the next event arrives

#### Scenario: SSE connection is severed
- **WHEN** no event arrives for >30 seconds
- **THEN** the indicator switches to red "已断开", a manual-reconnect affordance appears, and the dashboard falls back to 3-second polling if EventSource cannot re-establish

#### Scenario: SSE is unavailable in the environment
- **WHEN** EventSource construction fails or is not supported
- **THEN** the dashboard falls back to 3-second polling of the container and usage endpoints, and the connection indicator reflects polling-based freshness

### Requirement: Mobile polling strategy
On mobile viewports (< 1280px) the dashboard SHALL default to a 5-second polling interval for container status and usage data rather than maintain an SSE connection, in order to conserve battery.

#### Scenario: Mobile dashboard loads
- **WHEN** the dashboard detects a < 1280px viewport
- **THEN** it uses 5-second polling for container and usage data and does not open an EventSource connection

#### Scenario: Mobile operator backgrounds the page
- **WHEN** the mobile browser fires a visibilitychange to hidden
- **THEN** the dashboard pauses polling and resumes on visibilitychange to visible, reflecting any missed updates on the next poll

### Requirement: Message status display
Every team message rendered in the TeamChat shall display its delivery status: "已排队" for queued, "等待下次执行检查点" for injected (CLI engines) or "已送达" for injected (server engines), "已确认" for acknowledged, and "送达失败" for failed. The status SHALL transition in real time as SSE events report status changes and SHALL distinguish CLI-engine injection delay from server-engine injection.

#### Scenario: CLI engine message is injected
- **WHEN** a message targeting a CLI-engine session transitions from queued to injected via SSE
- **THEN** the message row shows "等待下次执行检查点" rather than a generic "已送达"

#### Scenario: Message reaches acknowledged
- **WHEN** a message's status changes to acknowledged with an `acknowledged_at` timestamp
- **THEN** the message row shows "已确认" with the timestamp and transitions to a terminal visual style

#### Scenario: Message delivery fails
- **WHEN** a message transitions to failed via SSE
- **THEN** the message row shows "送达失败" with a distinct error visual and a retry affordance where applicable

### Requirement: Chat input with session targeting
The TeamChat SHALL include a message composer that lets the operator target a specific session or the team broadcast channel, submit text messages, and see the message appear in the feed with "已排队" status within one poll/SSE cycle. The composer SHALL prevent submission of an empty message and SHALL disable itself when the team is paused or stopped.

#### Scenario: Operator sends a message to a session
- **WHEN** the operator selects a target session in the composer dropdown, types a message, and submits
- **THEN** `POST /api/work-containers/{id}/sessions/{sid}/messages` is called with the content, the message appears in the feed as "已排队", and the input clears

#### Scenario: Team is paused
- **WHEN** the team status is paused
- **THEN** the message composer is disabled with a label indicating that the team must be resumed first

### Requirement: Preserves existing visual direction
The dashboard SHALL reuse existing CSS component classes, color tokens, typography scale, spacing scale, and navigation shell from the BudgetLoop frontend. It SHALL NOT introduce a new design system, rebuild the nav bar, or alter the existing page routing hierarchy outside the `/containers/[id]` route.

#### Scenario: Dashboard renders within the operator workspace shell
- **WHEN** the container page loads
- **THEN** the BudgetLoop nav bar, product identity, and route hierarchy remain unchanged; only the `/containers/[id]` content area is replaced with the observatory layout

#### Scenario: Component styling is consistent
- **WHEN** any observatory component renders a badge, button, card, or status indicator
- **THEN** it uses the existing CSS utility classes and design tokens (colors, spacing, border-radius, typography) already in use by the operator workspace
