## Why

The current Agent Team flow always creates a manually configurable, hard-capped preset team. Operators who want a team to decompose work, collaborate in parallel, and decide when it is finished need a clear autonomous option without weakening the existing permission, approval, or audit boundaries.

## What Changes

- Add an explicit `autonomous` Agent Team mode selectable before a preset team is created; retain the existing guided setup as the default.
- In autonomous mode, give each enabled agent a trusted shared coordination contract: derive a focused subtask prompt from the goal and its role, work concurrently with eligible peers, and create auditable handoffs for dependent stages.
- Activate autonomous teams by their preset stages: dispatch a stage's independent roles in parallel, then automatically hand off completed stage output and release the next stage only after its dependencies complete.
- Add a `Max` budget choice for preset-team roles. It removes token, call, cost, wall-clock, active-runtime, and loop-iteration caps for that team while keeping accounting, explicit user stop/cancel, workspace isolation, approval controls, and AI completion judgement active.
- Clearly disclose unlimited-budget behavior in the setup and team views so it cannot be enabled accidentally.

## Capabilities

### New Capabilities

- `autonomous-agent-team-execution`: Mode-specific staged parallel execution, automatic handoff records, and completion-controlled activation for Agent Teams.
- `unlimited-agent-team-budget`: Explicit unlimited budget representation and enforcement semantics for autonomous Agent Teams.

### Modified Capabilities

- None.

## Impact

- Affects the Next.js Agent Team setup and detail presentation, preset creation/start API contract, session/run configuration, worker orchestration, budget accounting, and tests.
- Adds a database migration only if durable mode/budget metadata cannot remain in the existing versioned preset snapshot.
- Does not introduce new providers, expose provider credentials, bypass approval or folder-access policy, or change non-team task budgets.
