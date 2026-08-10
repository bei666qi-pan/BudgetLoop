# Judge Evaluation Loop Specification

## ADDED Requirements

### Requirement: Every active team has one visible system judge
The system SHALL provision exactly one visible, system-managed judge WorkSession for every new team, with an independent budget envelope and no product-file write permission. Startup recovery SHALL idempotently backfill active or paused teams while leaving historical terminal teams unchanged.

#### Scenario: New team provisioning
- **WHEN** a team is created
- **THEN** its response and observatory include one system judge Session and its budget/policy
- **AND** users cannot disable or delete that judge

#### Scenario: Recovery backfill
- **WHEN** startup observes an active or paused team without a judge
- **THEN** it creates one judge idempotently
- **AND** it does not mutate a terminal historical team

### Requirement: Deterministic gates precede model evaluation
Each round SHALL persist and execute required-role, message-confirmation, evidence, workspace, integration-publication, tests, build and artifact gates before any judge model call. A failed gate SHALL make `approve` impossible and SHALL produce targeted `rework` feedback.

#### Scenario: Hard gate failure
- **WHEN** any deterministic gate fails
- **THEN** the round verdict is `rework`, never `approve`
- **AND** no judge model evaluation is used to override the failure

#### Scenario: All gates pass
- **WHEN** every deterministic gate passes
- **THEN** the system invokes the real judge model for a strict structured verdict

### Requirement: Model verdicts are strict, durable and fail closed
The judge model SHALL return `approve | rework | blocked`, a summary, evidence-linked findings, responsible Session feedback and a next step. Invalid output, timeout, unavailable evidence or unavailable model SHALL be recorded and SHALL result in `blocked`, never a synthetic approval.

#### Scenario: Successful model approval
- **WHEN** all gates pass and the model returns a valid `approve`
- **THEN** the verdict, summary, findings and `llm_calls` usage are persisted

#### Scenario: Invalid or unavailable model
- **WHEN** the model times out, is unreachable or returns an invalid structure
- **THEN** the round is `blocked` with a visible sanitized reason
- **AND** the invalid/failed call is auditable

### Requirement: Rework is targeted and non-linear
The judge SHALL select responsible Sessions from current findings and may address multiple recipients in a round. Feedback SHALL use durable messages with real delivery/acknowledgement and Agent replies; the system SHALL NOT run a fixed round-robin script.

#### Scenario: Targeted rework
- **WHEN** a finding identifies a responsible Session
- **THEN** the judge sends that Session an evidence-linked request
- **AND** BudgetLoop starts a new TaskRun on the original Session branch
- **AND** the Session publicly acknowledges and replies before later review

### Requirement: Rework preserves cumulative safety boundaries
New TaskRuns SHALL carry the settled high-water mark of the original Session budget. Budget, runtime, rate or safety-round boundaries SHALL pause/ block for operator action rather than reset usage. An authenticated operator MAY explicitly add bounded recovery rounds or budget and resume.

#### Scenario: Budget recovery
- **WHEN** a Session reaches its envelope
- **THEN** execution pauses with saved state
- **AND** an increased envelope continues from cumulative usage

### Requirement: Judge state is available through team APIs and SSE
`GET /api/work-containers/{id}/judge` SHALL return the judge Session, policy, current state, complete round history, gates, findings and pending replies. Idempotent `POST /api/work-containers/{id}/judge/resume` SHALL evaluate or recover the next round. The durable team SSE stream SHALL include `judge_state_changed`, `judge_gate_completed`, `judge_feedback_dispatched` and `judge_verdict_recorded` with replay semantics.

#### Scenario: Replayed state
- **WHEN** the observatory reconnects
- **THEN** database state plus SSE replay reconstructs the same judge view without client-invented status

### Requirement: The observatory makes the judge loop visible
The existing three-column observatory SHALL render the judge as a special Session and group communication by judge round. It SHALL show evidence collection/gating/waiting/model-loading states, sender, recipient, message type, delivery state, gate results, model summary, failure reason and recovery control. It SHALL never render hidden reasoning or private context.

#### Scenario: Multi-Agent round display
- **WHEN** one round addresses multiple Agents
- **THEN** requests and responses are visibly grouped side-by-side by recipient
- **AND** delivery/acknowledgement and evidence are distinguishable from model conclusions

### Requirement: Desktop tracker delivery is accepted only after real E2E and judge approval
The formal team SHALL deliver `index.html`, `style.css` and `app.js` under `/Users/qi/Desktop/测试文件夹`, publish through the integration Session with primary `git merge --ff-only`, serve the result over HTTP, and pass desktop/390px Playwright checks for CRUD, summaries, deletion, validation, keyboard behavior, persistence, console/network health and overflow. Delivery SHALL require all hard gates and a real model-backed judge `approve`.

#### Scenario: Final acceptance
- **WHEN** the published tracker and BudgetLoop suites/build are green
- **THEN** the judge may approve using those exact evidence references
- **AND** local URLs and screenshot evidence are retained for handoff
