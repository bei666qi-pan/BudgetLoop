## 1. Database Migrations

- [x] 1.1 Add `message_type`, `idempotency_key`, `acknowledged_at` columns to `session_messages` table
- [x] 1.2 Change `delivery_state` default to `queued`, add unique index on `idempotency_key` WHERE NOT NULL
- [x] 1.3 Create `team_audit_events` table (container_id, session_id, action, old_value, new_value, operator, created_at)
- [x] 1.4 Create `session_progress_signals` table (session_id, run_id, summary, milestone, completed_items, next_step, blocked, blocker_reason, needs_operator, evidence, iteration, created_at)
- [x] 1.5 Add `container_id` column to `execution_events` table with index WHERE NOT NULL
- [x] 1.6 Run Alembic migration and verify schema in PostgreSQL

## 2. Backend: Message State Machine & Anti-Runaway

- [x] 2.1 Update `SessionMessage` ORM model with new columns (message_type, idempotency_key, acknowledged_at)
- [x] 2.2 Implement message state transition logic in `app/collaboration/service.py`: queued→injected→acknowledged/failed with atomic SQL UPDATE
- [x] 2.3 Add idempotency handling in `POST /api/work-containers/{id}/sessions/{sid}/messages`: return existing on duplicate key
- [x] 2.4 Add sender validation: prohibit self-send (sender != recipient), cross-container delivery, delivery to terminated sessions
- [x] 2.5 Implement anti-runaway hard limits: 30 msgs/min rate limit (Valkey TTL), 5-round auto-reply limit (worker counter), 5% budget Token cap
- [x] 2.6 Add anti-broadcast guard: each message must have exactly one explicit recipient
- [x] 2.7 Implement auto-reply pause on limit breach + `team_audit_events` recording + frontend notification event
- [x] 2.8 Add `GET /api/work-containers/{id}/messages/{msg_id}/acknowledge` endpoint for Agent confirmation
- [x] 2.9 Write pytest: message state machine full cycle, idempotency, self-send rejection, cross-container rejection, rate limit enforcement, round limit, Token cap, broadcast rejection

## 3. Backend: CLI Safety Checkpoint Injection

- [x] 3.1 Extend `CLIEngineAdapter` with `check_injection_point()` method detecting iteration start/end boundaries
- [x] 3.2 Extend `CLIEngineAdapter` with `extract_progress_signal()` method parsing structured progress from iteration output
- [x] 3.3 Update worker orchestrator to call `check_injection_point()` before each CLI iteration, inject queued messages
- [x] 3.4 Mark messages as `injected` at inject point (not `delivered`); only mark `acknowledged` on Agent `send_message` confirmed
- [x] 3.5 Implement "等待下次执行检查点" status label via honest injected-but-not-acknowledged detection
- [x] 3.6 Write pytest: CLI injection timing, queued→injected transition, acknowledged only on Agent confirmation, progress signal extraction

## 4. Backend: Team Usage Aggregation

- [x] 4.1 Implement `GET /api/work-containers/{id}/usage` endpoint: aggregate `task_budgets` SUM across active sessions
- [x] 4.2 Exclude completed/failed/cancelled sessions' reserved from team reserved total
- [x] 4.3 Compute consumption rate (tokens/min from trailing 5-min `llm_calls` window) and estimated depletion time
- [x] 4.4 Compute team pressure mode: take the worst (most tense) of all active sessions
- [x] 4.5 Include per-session breakdown: used/reserved/remaining/max for tokens, cost, calls, wall-time, active-time
- [x] 4.6 Include token sub-types from `llm_calls`: prompt/completion/reasoning/cache_read/cache_write
- [x] 4.7 Handle missing fields: return `null` for absent optional fields (cost, ttft, cache), never 0
- [x] 4.8 Ensure no double-counting: team aggregate = arithmetic SUM of per-session `task_budget.used_*`, no re-settlement
- [x] 4.9 Write pytest: aggregation correctness, reserved exclusion for terminal sessions, pressure mode bounds, missing field null handling, consumption rate calculation

## 5. Backend: Team Progress Observability

- [x] 5.1 Implement `session_progress_signals` ORM model
- [x] 5.2 Implement `GET /api/work-containers/{id}/progress` endpoint: aggregate latest progress from all sessions
- [x] 5.3 Compute team summary: running/waiting/paused/blocked/completed counts, active stage, recent milestones (top 10)
- [x] 5.4 Compute per-session progress: status, phase, current public action, last activity, milestones, next_step, blocked, needs_operator, evidence, iteration
- [x] 5.5 Percentage display logic: only show percentage when explicit finite `completed_items` with known total count
- [x] 5.6 Ensure no LLM calls are made for progress refresh (pure PostgreSQL query)
- [x] 5.7 Write pytest: team progress aggregation, per-session progress, percentage logic, missing signal fallback, no LLM call

## 6. Backend: Team Runtime Control

- [x] 6.1 Implement `POST /api/work-containers/{id}/pause`: idempotent, pause all RUNNING sessions, block new dispatch from QUEUED/PENDING
- [x] 6.2 Implement `POST /api/work-containers/{id}/resume`: idempotent, resume paused sessions, re-evaluate autonomous stage dispatch
- [x] 6.3 Implement `POST /api/work-containers/{id}/stop`: require confirmation header, terminate all runs, mark container completed
- [x] 6.4 Implement `POST /api/work-containers/{id}/sessions/{sid}/resume`: idempotent session-level resume
- [x] 6.5 Implement `PATCH /api/work-containers/{id}/budget`: enforce `new_max >= used + reserved` constraint, 422 on violation
- [x] 6.6 Implement `PATCH /api/work-containers/{id}/sessions/{sid}/budget`: session-level budget adjustment with same constraint
- [x] 6.7 Implement `POST /api/work-containers/{id}/correct`: inject correction instruction as high-priority system message
- [x] 6.8 Budget increase `needs_resume: true` flag after exhaustion recovery; `needs_resume: false` for active session
- [x] 6.9 Lowering `max_parallel_llm_calls`: only affects new requests, in-flight calls not interrupted
- [x] 6.10 GUIDED/AUTONOMOUS runtime switch: require `mode_switch_confirmed` header, explain impact in response
- [x] 6.11 Write ALL control operations to `team_audit_events` (old_value, new_value, operator)
- [x] 6.12 In-flight LLM call handling: pause waits for in-flight to complete, does not kill mid-call
- [x] 6.13 Autonomous resume: re-evaluate stage dependencies before dispatching eligible stages
- [x] 6.14 Write pytest: idempotent pause/resume/cancel, budget floor rejection, needs_resume flag, parallelism only on new, audit event creation, mode switch confirmation, autonomous re-evaluation

## 7. Backend: Team SSE Event Stream

- [x] 7.1 Implement `GET /api/work-containers/{id}/stream` SSE endpoint: query `execution_events` WHERE container_id = X
- [x] 7.2 Support `Last-Event-ID` header for reconnection replay (incremental from last_seq)
- [x] 7.3 Filter events: exclude null container_id events (legacy single-run events)
- [x] 7.4 Cap single event payload at 4KB
- [x] 7.5 Emit `session_progress` event on new `session_progress_signals` insert
- [x] 7.6 Emit `budget_pressure_change` event on threshold crossing (NORMAL→CONSERVATIVE, CONSERVATIVE→CRITICAL, and reverse)
- [x] 7.7 Emit `team_control_audit` event on any control operation (pause/resume/stop/budget/correct)
- [x] 7.8 Emit `session_status_change` event on session run status transitions
- [x] 7.9 Write pytest: SSE event emission, Last-Event-ID replay, payload size cap, null container_id exclusion, event type correctness

## 8. Frontend: Team Observatory Dashboard Core

- [x] 8.1 Create `TeamObservatoryDashboard` component as replacement for `/containers/[id]/page.tsx`
- [x] 8.2 Implement desktop three-panel CSS Grid layout: SessionRail (w-72), TeamChat (flex-1), Inspector (w-80)
- [x] 8.3 Implement mobile three-tab layout at <1280px: 成员/对话/控制 with horizontal tab bar, no overflow at 390px
- [x] 8.4 Implement cross-tab alert banner: approval requests, blocking, overspend warnings visible regardless of active tab
- [x] 8.5 Create top bar component: team status badge, phase label, aggregated tokens/cost/time, connection indicator, pause/resume/stop buttons
- [x] 8.6 Implement SSE connection with EventSource: green (connected), amber 10s ("数据可能过期"), red 30s ("已断开") + polling fallback
- [x] 8.7 Mobile: 5s polling strategy with visibilitychange pause/resume
- [x] 8.8 Reuse existing `.surface`, `.badge`, `.btn`, `.data-table`, `.card` CSS component classes from globals.css
- [x] 8.9 Preserve `AppShell` navigation and shell structure unchanged
- [x] 8.10 Write Vitest: layout at 1280px and 390px, tab switching, alert cross-tab, SSE connection states, polling fallback

## 9. Frontend: Session List (SessionRail)

- [x] 9.1 Create `TeamSessionRail` component: sorted session list with status indicator, current action, pressure level
- [x] 9.2 Display per-session: status dot (color-coded), role name, current phase, last activity time, token usage bar, pressure badge
- [x] 9.3 Sort: CRITICAL sessions first, then CONSERVATIVE, then NORMAL; within same pressure by last activity
- [x] 9.4 Highlight selected session; clicking a session updates center panel (TeamChat) and right panel (Inspector)
- [x] 9.5 Show alert icon on sessions with `blocked=true` or `needs_operator=true`
- [x] 9.6 Filter dropdown: all messages, @me, blocked only
- [x] 9.7 Include "New Session" button (reuse existing CreateSessionDialog)
- [x] 9.8 Write Vitest: sort order, selection highlight, alert indicators, filter functionality

## 10. Frontend: Team Chat (TeamChannel)

- [x] 10.1 Create `TeamChannel` component: chronological message stream with sender, type, time, status
- [x] 10.2 Message type rendering: 💬 message, 📤 handoff, 📋 progress_update, ⚠ system_fact (with distinct visual treatment)
- [x] 10.3 Status labels: "已排队" (queued), "等待下次执行检查点" (injected/CLI), "已送达" (acknowledged/server), "送达失败" (failed)
- [x] 10.4 Handoff rendering: show conclusion, evidence, open_questions, next_step sections; no hidden reasoning
- [x] 10.5 Progress update rendering: show summary, milestone, completed items count, next step; blocked indicator
- [x] 10.6 Chat input: message composer with @target session selector dropdown, message type selector
- [x] 10.7 Filter conversation by: team channel (all messages), or single session conversation
- [x] 10.8 Message dedup: frontend ignores duplicate idempotency_key on optimistic update
- [x] 10.9 Disable chat input when team is paused
- [x] 10.10 Write Vitest: message rendering by type, status labels, handoff sections, filter, paused state

## 11. Frontend: Inspector Panel (Progress, Usage, Control)

- [x] 11.1 Create `TeamInspector` component with collapsible sections: 进度, 用量, 控制
- [x] 11.2 Progress section: team summary (counts by status, active stage, next focus), selected session detail (status/phase/action/milestones/next_step/blocked/evidence/iteration)
- [x] 11.3 Progress display rules: percentage only for explicit finite milestones, "进行中" with count for open-ended, "Agent 未声明进度" for no signals
- [x] 11.4 Usage section default (collapsed detail): tokens used/remaining with progress bar, cost, wall time, health badge (NORMAL/CONSERVATIVE/CRITICAL)
- [x] 11.5 Usage section expanded: prompt/completion/reasoning/cache tokens, calls count, active time, parallelism, consumption rate, estimated depletion
- [x] 11.6 Missing field handling: "未上报" label for null cost, null rate, null cache tokens (never 0)
- [x] 11.7 Control section team-level: pause/resume/stop buttons, budget adjustment (current→new with preview), parallelism adjustment
- [x] 11.8 Control section session-level: pause/resume/cancel buttons, budget adjustment, append instruction text input
- [x] 11.9 Budget adjustment flow: show old→new values, confirm dialog, API call, rollback on failure
- [x] 11.10 Budget post-exhaustion: show "已增加预算，请点击恢复" when `needs_resume: true`
- [x] 11.11 Cancel requires confirmation dialog: explain irreversibility
- [x] 11.12 Guided/autonomous switch: explain impact, require explicit confirmation
- [x] 11.13 Write Vitest: collapsible sections, progress rules, missing fields, control flows, confirmation dialogs, needs_resume button

## 12. Frontend: Team Status in Container List

- [x] 12.1 Update `GET /api/containers` response to include `team_status`, `active_session_count`, `alert_count` per container
- [x] 12.2 Update container list page to show team status badge (running/paused/blocked/stopped) per row
- [x] 12.3 Show alert count badge with click-to-navigate to team observatory
- [x] 12.4 Click container row navigates to `/containers/[id]` (team observatory, not old workspace)
- [x] 12.5 Write Vitest: status badges, alert count, navigation

## 13. Frontend: Run Page Container/Session Context

- [x] 13.1 Add breadcrumb to run detail page: Agent Team → Container Name → Session Role → Run (when container-owned)
- [x] 13.2 Show team-level control context in run page: "此 Run 属于团队 XXX，当前团队状态: 运行中/已暂停"
- [x] 13.3 Show session progress signals in run detail when available (from `session_progress_signals`)
- [x] 13.4 Preserve standalone run behavior (no container context) unchanged
- [x] 13.5 Write Vitest: breadcrumb rendering, team context display, progress signals display

## 14. Agent Coordination Protocol (Prompt-Level)

- [x] 14.1 Draft coordination protocol prompt fragment: role-goal scoping, concise messaging, milestone-only progress, blocking declaration, no-liveness-repeat, escalation rule, budget-pressure adaptation, evidence-backed completion
- [x] 14.2 Inject protocol into worker iteration instruction for all container-owned sessions
- [x] 14.3 Inject pressure-adaptive guidance (reduce exploration, reuse evidence, prioritize acceptance) based on current pressure mode
- [x] 14.4 Verify protocol does not grant tool access, permissions, or cross-session context (only constrains behavior)

## 15. Backward Compatibility & Integration

- [x] 15.1 Ensure old container workspace page component retained but route replaced by team observatory
- [x] 15.2 Verify existing single-task Run pages unchanged (no container_id → no team context)
- [x] 15.3 Verify existing API endpoints add new fields without removing/renaming existing fields
- [x] 15.4 Verify old clients ignoring unknown fields continue to function
- [x] 15.5 Verify `GET /api/runs/{id}/stream` still works for legacy runs (container_id = NULL)
- [x] 15.6 Verify `POST /api/work-containers/from-preset` works with new message fields

## 16. Tests & Verification

- [x] 16.1 Run `cd backend && pytest` — all existing and new tests pass
- [x] 16.2 Run `cd web && npm test` — all existing and new tests pass
- [x] 16.3 Run `cd web && npm run build` — no TypeScript or build errors
- [x] 16.4 Test mobile layout at 390px viewport: no horizontal overflow, all tabs functional
- [x] 16.5 Test keyboard navigation: tabs, message input, control buttons
- [x] 16.6 Test screen reader: status labels, alert descriptions, progress annoucements
- [x] 16.7 Test reduced-motion: all animations disabled
- [x] 16.8 Test SSE disconnect/reconnect: stale data warning, Last-Event-ID replay, polling fallback
- [x] 16.9 Test audit trail: verify `team_audit_events` contains all operator control actions with correct old/new values
- [x] 16.10 Test budget floor: PATCH below used+reserved returns 422
- [x] 16.11 Test idempotency: double pause/resume/cancel returns success without side effects
- [x] 16.12 Test private context isolation: cross-session transcript shows no other session's private_context
- [x] 16.13 Test anti-runaway: message flood triggers auto-reply pause, audit event recorded
- [x] 16.14 Test legacy run regression: create and run single task (no container) — unchanged behavior
