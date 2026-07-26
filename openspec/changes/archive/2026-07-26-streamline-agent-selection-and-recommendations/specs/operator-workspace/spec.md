## ADDED Requirements

### Requirement: Progressive conversational review hierarchy
The operator workspace SHALL keep goal, team, engine, folder access, and the primary confirmation action visible while placing implementation-oriented recommendation, topology, role-budget, gateway, and audit detail behind progressive disclosure.

#### Scenario: Beginner reviews a successful AI draft
- **WHEN** a valid AI-backed draft is ready
- **THEN** the review presents a concise ready state and primary next action without a prominent gateway or implementation-detail card

#### Scenario: Local fallback produces a usable draft
- **WHEN** AI genuinely fails and local recommendation produces a valid draft
- **THEN** the review shows a compact neutral provenance status with optional sanitized detail and does not visually treat the draft as an error

#### Scenario: Operator needs advanced detail
- **WHEN** the operator expands advanced configuration or provenance
- **THEN** role, budget, engine-readiness, approval, permission, and recommendation facts remain inspectable and editable within existing enforcement bounds

### Requirement: Recent-history deletion interaction
The recent-work region SHALL expose a secondary delete action for eligible terminal standalone tasks, require a task-specific confirmation, and preserve the row with error feedback until deletion succeeds.

#### Scenario: Operator confirms task deletion
- **WHEN** an eligible task's delete action is activated and the named confirmation is accepted
- **THEN** the interface waits for the API result and removes only that task row after success

#### Scenario: Task cannot be deleted
- **WHEN** the API rejects deletion because the task is active or team-owned
- **THEN** the row remains present and the interface explains the lifecycle or ownership restriction without exposing backend internals
