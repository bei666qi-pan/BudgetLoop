## Context

BudgetLoop currently has a strong execution boundary at `task_run`: every run owns an OpenHands conversation, budget ledger, event stream and isolated Docker workspace. That boundary must remain intact. The missing layer is project coordination—operators cannot group several runs under one shared outcome, assign roles, retain independent session context or pass a controlled handoff between agents.

The new domain is additive. A work container is a durable project/team scope. A work session is an independently owned agent lane backed by one normal BudgetLoop task and its current run. PostgreSQL remains authoritative; Valkey remains transport/queue only; OpenHands remains the conversation executor.

## Goals / Non-Goals

**Goals:**

- Represent a project Agent team as one work container containing several independently observable sessions.
- Keep session goal, private context, conversation transcript, run state and optional worktree identity isolated.
- Share only container goal/context and explicit messages or handoffs.
- Deliver queued messages into the recipient OpenHands conversation at a deterministic iteration boundary.
- Reuse existing budgets, approvals, reports, worker queue and Docker workspace security.
- Provide a clear, responsive UI for team overview, session switching, conversation, handoff and runtime visibility.

**Non-Goals:**

- Autonomous unrestricted agent-to-agent API calls or shared hidden chain-of-thought.
- Automatic branch merging, conflict resolution or Git hosting integration.
- Replacing the existing task dashboard or single-task creation route.
- Multi-user RBAC, external chat connectors, distributed scheduling or a new event broker.

## Decisions

### 1. Add a coordination layer instead of changing the meaning of tasks

`WorkContainer` owns shared project intent and `WorkSession` owns one specialist lane. Creating a runnable session also creates a normal `Task` and `TaskRun`; `WorkSession.current_run_id` links the coordination UI to existing execution. Existing task/run endpoints remain valid for sessions created outside a container.

Alternative considered: make a container a special Task with child runs. Rejected because child runs would still lack distinct goals, message ownership and independent histories, and it would overload retry semantics.

### 2. Persist collaboration as an explicit inbox

`SessionMessage` stores container, recipient, optional sender session, author type, kind (`message` or `handoff`), content, delivery state, idempotency key and timestamps. Messages are recipient-specific; there is no implicit access to another session's private context. Container activity is derived from these records and run state rather than maintained as a second source of truth.

Alternative considered: copy all session transcripts into shared context. Rejected because it destroys isolation, grows prompts without bound and makes provenance unclear.

### 3. Deliver at iteration boundaries with at-least-once identity

Before `build_iteration_instruction`, the orchestrator queries queued messages for the run's owning session and adds a compact, ID-labelled inbox section. After `send_message` succeeds, the same transaction marks them delivered and emits a collaboration event. A failed send leaves messages queued. Duplicate delivery remains recognizable by immutable message ID, while unique idempotency keys prevent duplicate API submissions.

Alternative considered: push messages directly into a running OpenHands conversation from the API process. Rejected because it races the worker loop and bypasses budget/run state coordination.

### 4. Store a session transcript without claiming hidden reasoning

User and handoff messages are stored directly. Agent-visible transcript entries are generated from the existing public `AGENT_MESSAGE` execution events or explicit summaries only. The UI labels those entries as Agent output and never exposes hidden reasoning or another session's private context.

### 5. Optional worktree lives inside the existing isolated workspace

Every run still receives a Docker workspace. When `worktree_enabled` is true, `WorkspaceManager` creates a sanitized branch and Git worktree under `.budgetloop/worktrees/<session-id>` after repository initialization and returns that directory as the OpenHands working directory. When false, the normal workspace root is used. Worktree path and branch are persisted on the session for observability. Failures stop the run with an actionable workspace error rather than silently falling back.

Alternative considered: host-level worktrees shared by several containers. Rejected for the first version because the worker deployment does not mount arbitrary host repositories and sharing them would weaken the current isolation model.

### 6. API shape is additive and nested by ownership

- `GET/POST /api/work-containers`
- `GET/PATCH /api/work-containers/{container_id}`
- `POST /api/work-containers/{container_id}/sessions`
- `GET /api/work-containers/{container_id}/sessions/{session_id}`
- `POST /api/work-containers/{container_id}/sessions/{session_id}/messages`
- `POST /api/work-containers/{container_id}/sessions/{session_id}/pause`

All routes use existing bearer authentication, validate nested ownership and return 404 rather than leaking foreign identifiers. Session creation accepts the existing strategy/budget/safety fields and uses an idempotency key.

### 7. Frontend uses a three-region team workspace

The container detail page keeps one clear hierarchy: project/team status at top; session rail for switching and creation; selected session goal/conversation in the primary region; shared context, inbox and worktree/runtime facts in the supporting region. Desktop uses three coordinated regions without nested-card excess; mobile uses one selected session with compact tabs and reachable handoff/create actions. Existing light-blue tokens, typography, buttons and status treatments remain the visual source of truth.

### 8. Performance and refresh model

Container detail loads container, sessions and selected transcript in parallel where possible. Initial implementation uses a short polling interval and stable message/session IDs; no new WebSocket channel is required. Long lists use bounded queries and pagination-ready response shapes.

## Risks / Trade-offs

- [A message may be delivered twice if the worker crashes after sending but before commit] → Include immutable message IDs in the prompt, make API submission idempotent and expose delivery state honestly.
- [Session teams can multiply total cost] → Preserve an independent hard budget per session and show aggregate usage as a derived summary; no shared budget pool is introduced silently.
- [Worktree creation may fail for non-Git or unusual repositories] → Validate Git state, return an explicit failed workspace state and keep the non-worktree option available.
- [Cross-session context can leak private data] → Only explicit message content crosses the boundary; private context and full transcripts are never copied automatically.
- [Polling can become expensive with many sessions] → Load summaries at container level, fetch the selected transcript separately and cap message page size.
- [Container status can drift if stored independently] → Store only explicit lifecycle state; derive live/attention counts from current run/session records.

## Migration Plan

1. Add nullable coordination tables and optional indexes without altering existing task/run rows.
2. Deploy API serialization and creation paths; legacy workflows remain unchanged.
3. Deploy worker inbox delivery and optional worktree creation guarded by nullable ownership.
4. Deploy frontend routes and navigation.
5. Backfill is unnecessary; existing tasks remain ungrouped. Rollback removes the new routes/worker behavior while leaving additive tables inert.

## Open Questions

- A future version may add container-wide budget pools and automated merge sessions, but neither is implied by this change.
- A future event-stream extension may replace polling once container usage justifies it.
