## Context

Preset teams already contain a trusted role catalog and a LangGraph-derived ordered topology, but startup dispatches every run and handoffs are operator-created. Each run is bounded by six hard budget values and a loop cap. The requested mode must let a team coordinate itself without turning model output into authority over folders, approvals, provider credentials, or durable state.

The existing Agent Team collaboration model and its recipient-scoped `SessionMessage` table remain the source of truth for communication. The staged topology follows the existing LangGraph activation design in `backend/app/team_presets/activation.py`; no new agent framework or external dependency is needed.

## Goals / Non-Goals

**Goals:**

- Provide an explicit, opt-in autonomous setup mode before a preset team starts.
- Run roles in the same eligible stage concurrently and release dependent stages only after successful predecessor completion.
- Deliver generated, auditable handoff messages from completed public agent output to eligible downstream roles.
- Support a truthful `Max` budget mode: no automatic token, call, cost, time, or loop ceiling; an operator can still pause/cancel and normal acceptance evaluation can finish the run.
- Preserve existing guided teams and all permission, approval, engine-readiness, idempotency, and accounting behavior.

**Non-Goals:**

- No model receives new tool permissions, cross-session private context, credentials, or direct database access.
- No unbounded retry daemon, autonomous container deletion, or automatic approval of risky actions.
- No change to standalone task budget contracts or an AI-generated replacement for the trusted preset catalog.

## Decisions

### Persist mode in the existing applied snapshot and run configuration

`preset_snapshot` will contain public `team_mode` (`guided` or `autonomous`) and `budget_mode` (`bounded` or `max`). Every created run receives the same concise immutable configuration in `model_config`. This is versioned with the existing team snapshot and needs no schema migration.

Alternative: new database columns. Rejected because creation, audit APIs, and compatibility already use the immutable JSONB snapshot and a normalized query/filter is not required.

### Reuse the preset activation graph as the autonomous scheduler

For an autonomous team, start dispatch only submits roles in dependency-free stages. Roles in one eligible stage are submitted together. When a source role ends `COMPLETED`, the worker records one recipient-specific handoff for each dependent role using the agent's public output summary, then attempts release of a dependent stage only when every role in every prerequisite stage is `COMPLETED`.

The release operation is idempotent: handoff metadata carries the source/target run pair and the existing dispatch snapshot prevents a run from being queued twice. Failed, cancelled, paused, or budget-exhausted predecessors never unlock their dependents; the operator retains normal recovery controls.

Alternative: dispatch every role and tell the model to coordinate in text. Rejected because it cannot guarantee dependency ordering or show trustworthy delivery state.

### Make autonomy a bounded instruction contract, not a new privilege

Autonomous runs get a visible instruction that they must derive and maintain a role-focused execution plan from the project goal, work independently within their assigned workspace, publish concise factual output for handoff, and finish when their acceptance evidence is met. The scheduler only consumes public output; it never shares private contexts. The existing worker remains the authority for state transitions, policy gates, and final reporting.

### Represent `Max` as a budget mode rather than fake high numeric ceilings

Budget columns keep valid values for compatibility and accounting, while `model_config.budget_mode == "max"` tells run creation to omit the deadline, budget reservation to bypass all cap comparisons, pressure calculation to remain normal, phase reallocation to skip cap decisions, and the loop to omit its iteration ceiling. Usage is still settled and reported. API budget snapshots expose `unlimited: true`, allowing the UI to show `Max` rather than a misleading large number.

Alternative: use integer maximum values. Rejected because it is not actually unlimited and makes usage/remaining displays deceptive. Alternative: nullable budget columns. Rejected because it requires broad schema, SQL, and compatibility changes.

## Risks / Trade-offs

- [A completed model output is incomplete or low quality] → Existing acceptance checks, approval gates, public transcript, and final report remain active; completion unlocks only explicitly declared downstream stages.
- [A worker crashes between handoff and dispatch] → Transactional message persistence plus idempotency metadata and dispatch tracking make a later start/recovery attempt safe.
- [Unlimited use surprises an operator] → `Max` is a separate explicit setup choice with a warning; the detail view labels it continuously, and normal pause/cancel endpoints remain available.
- [An autonomous team stalls after a failed predecessor] → Do not silently continue dependent work; surface the existing attention state and leave recovery to the operator.

## Migration Plan

1. Deploy backwards-compatible request defaults (`guided`, `bounded`) and snapshot parsing.
2. Deploy UI controls and worker support. Existing containers have no mode fields and behave as guided bounded teams.
3. Verify database migration is unnecessary because no persisted column changes are introduced.
4. Roll back by disabling the UI selection; existing autonomous snapshots remain readable and retain their explicit run behavior.

## Open Questions

- None for the initial implementation. “AI decides to stop” is implemented through the existing acceptance/finished evaluation, not by trusting hidden reasoning or allowing an uncontrolled worker loop.
