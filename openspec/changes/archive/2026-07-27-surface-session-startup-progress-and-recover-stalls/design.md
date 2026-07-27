## Context

The worker transitions a run to `PLANNING` before provisioning its OpenHands agent-server workspace. `WorkspaceManager._wait_healthy` polls the published health endpoint, but it produces no persisted progress while it waits. If Docker Desktop's published-port proxy returns a persistent `502`, the operator sees only a static planning state. The existing workspace manager raises after a bounded wait, but state is only updated by the generic failure path and is not visible until then.

The Agent Team page already polls a container and selected session every five seconds. It receives the session status, workspace status/error, run timestamps, and transcript, so it can present truthful feedback without creating a second state store or simulated percentage.

## Goals / Non-Goals

**Goals:**

- Bound agent-server health startup and persist the active workspace phase before waiting.
- Convert startup exceptions into a failed workspace/session/run with a sanitized action-oriented message.
- Show a compact, branded live startup panel with stages and elapsed time, followed by an error panel when startup fails.
- Keep README English first and offer an equivalent Chinese document through explicit language links.

**Non-Goals:**

- Retrying or restarting a failed run automatically.
- Inferring container health from browser-side timing or reporting fabricated completion percentages.
- Changing direct-folder permission semantics, provider credentials, Docker networking, or the database schema.

## Decisions

### Persist only the existing lifecycle state

The orchestrator will set `workspace_status=PROVISIONING` and commit before calling the workspace manager. Its generic failure handler will set `workspace_status=FAILED` and persist the sanitized error. This uses PostgreSQL as the existing source of truth and makes the state visible even if provisioning blocks. A separate event stream or a new progress table would add duplicated lifecycle state without improving the failure boundary.

### Treat a non-200 health endpoint as startup evidence, not success

The workspace manager will retain bounded health polling but capture the last transport/status diagnosis in its error. It will not treat `502` as a transient success or continue indefinitely. The orchestrator catches the resulting `WorkspaceError`, marks the run failed, and removes the created agent-server container. This maintains fail-closed execution and gives the operator a meaningful next action: retry after checking Docker / the agent-server image.

### Derive UI stages deterministically

The frontend maps existing data to a short sequence: queued, provisioning workspace, workspace ready / starting agent, then active execution. `workspace_status=FAILED` or an error terminal session becomes an alert with the persisted error. The start time comes from the selected session's run detail and is refreshed through the existing polling cadence. No percentage or timer is presented as backend work completed.

### Reuse the existing BudgetLoop activity mark

The startup panel uses the shared `BudgetLoopActivityMark`, including its reduced-motion behavior and accessible live text. The page keeps loading skeletons only for initial data retrieval; once session data exists, it uses lifecycle-specific feedback instead.

### Follow mature OSS README conventions without copying content

The primary README uses an English tagline, badges, language switch, quick start, architecture, security, contributing, and license sections. `README.zh-CN.md` contains the Chinese counterpart and links back. Project-specific commands stay exact; documentation does not claim unsupported deployment or guarantees.

## Risks / Trade-offs

- [A transient Docker Desktop proxy issue can fail a run that might recover later] → a bounded, visible failure is preferable to indefinite hidden waiting; operators can retry intentionally after infrastructure recovery.
- [The session-detail API may lack a start timestamp on newly created sessions] → the UI displays “just started” until a persisted run timestamp is available rather than inventing elapsed time.
- [Polling updates are not instantaneous] → the panel explains the current known server state and preserves the existing five-second refresh behavior.
- [Changing README structure risks stale setup instructions] → retain only commands verified against the compose configuration and link detailed Chinese material rather than duplicating contradictory snippets.

## Migration Plan

1. Deploy worker and web changes together; no migration is needed.
2. New sessions immediately persist provisioning and failures. Existing sessions retain their recorded terminal state.
3. If a regression occurs, revert the application images; state fields are unchanged and remain compatible.

## Open Questions

None. A future explicit retry action can be proposed separately once safe replay semantics are defined.
