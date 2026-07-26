## Why

BudgetLoop currently treats each task run as an isolated unit, which makes it difficult to coordinate several specialized agents on one project without losing ownership, context boundaries, or auditability. A work-container layer can turn those isolated runs into a deliberate project team: each session keeps its own conversation, goal, context and runtime while sharing only explicit, traceable handoffs.

## What Changes

- Add persistent work containers that hold a project-level goal, shared context, lifecycle state, workspace policy and a collection of independently runnable sessions.
- Add work sessions with a role, private goal/context, conversation history, run linkage, status and optional isolated Git worktree metadata.
- Add explicit cross-session messages and handoffs with sender, recipient, delivery state and immutable audit metadata; sessions remain isolated by default.
- Inject unread handoff summaries into the recipient Agent conversation before its next execution step and mark delivery transactionally, without exposing another session's full private context.
- Add authenticated REST endpoints for work-container, session, message and handoff lifecycle operations while keeping the existing task/run APIs backward compatible.
- Add a light-blue “Agent Team” workspace in the Next.js UI with container overview, team/session topology, session conversation, shared context, runtime status and worktree visibility.
- Add database migrations, backend and frontend tests, API-contract documentation, responsive behavior and trustworthy empty/error/partial states.
- Preserve existing per-run budgets, approvals, Docker isolation, PostgreSQL ownership and provider-key security boundaries.
- Non-goals: autonomous unrestricted agent-to-agent tool invocation, merging Git branches automatically, replacing OpenHands conversation execution, multi-user permissions, external chat integrations, or distributed worker scheduling.

## Capabilities

### New Capabilities

- `work-container-lifecycle`: Project-level work containers, membership, shared goal/context, lifecycle state and workspace policy.
- `team-session-collaboration`: Independent Agent sessions, private conversation/context, explicit cross-session messages, handoff delivery and run linkage.
- `isolated-session-workspaces`: Optional per-session Git worktree identity and safe lifecycle behavior on top of the existing isolated workspace runtime.

### Modified Capabilities

- `operator-workspace`: Extend the shared shell and task discovery experience with an Agent Team entry point and container-aware navigation without removing the legacy task workflow.
- `run-command-center`: Expose a run's owning work container/session and safely consume explicit handoff context before an Agent iteration.

## Impact

- Backend: new SQLAlchemy models, Alembic migration, serializers, authenticated FastAPI routes, message delivery service, orchestrator context injection and workspace/worktree helpers.
- Frontend: new `/containers`, `/containers/new`, and `/containers/[id]` routes, shared navigation, types, presentation helpers and interactive session/message controls.
- API: additive `/api/work-containers` and nested session/message endpoints; existing task and run payloads gain optional ownership fields only.
- Data: PostgreSQL remains the single business source of truth; message delivery uses explicit states and unique constraints for idempotency.
- Safety and budget: each session continues to use a normal task run and its budget/approval controls; shared context does not grant cross-workspace filesystem access.
- Infrastructure: no new service dependency. Optional worktree setup is performed inside the existing session workspace and degrades to an actionable failed state when Git prerequisites are unavailable.
