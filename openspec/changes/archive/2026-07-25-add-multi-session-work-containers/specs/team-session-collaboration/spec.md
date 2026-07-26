## ADDED Requirements

### Requirement: Independent agent session
Each work session SHALL own a role, goal, private context, conversation identity, current task/run linkage and runtime status that can be inspected without revealing another session's private context.

#### Scenario: Operator creates a runnable session
- **WHEN** valid role, goal, safety, strategy and budget values are submitted under a container
- **THEN** the system atomically creates the session, task, run and budget records and enqueues only that run

#### Scenario: Session creation is retried
- **WHEN** the same idempotency key is submitted again
- **THEN** the existing session and run are returned without creating or enqueuing duplicates

### Requirement: Explicit cross-session message
The system SHALL allow an operator or another session identity in the same container to send a message or handoff to one recipient session with immutable provenance and delivery state.

#### Scenario: Handoff is queued
- **WHEN** a sender selects a different session in the same container and submits non-empty handoff content
- **THEN** one queued message is stored with sender, recipient, kind, content and creation time

#### Scenario: Cross-container recipient is attempted
- **WHEN** the sender or recipient does not belong to the owning container
- **THEN** the message is rejected and no content crosses the container boundary

### Requirement: Controlled Agent inbox delivery
The worker SHALL add queued recipient messages to the next Agent iteration as a compact ID-labelled inbox and SHALL mark them delivered only after the Agent message request succeeds.

#### Scenario: Recipient begins the next iteration
- **WHEN** one or more queued messages exist for the session's current run
- **THEN** their explicit content and provenance are appended to the iteration instruction and a delivery event is recorded

#### Scenario: Agent message request fails
- **WHEN** the worker cannot submit the iteration message
- **THEN** inbox messages remain queued and the system does not claim successful delivery

### Requirement: Auditable session transcript
The session UI SHALL present user messages, explicit handoffs and public Agent output in chronological order with author, target, timestamp and delivery semantics.

#### Scenario: Operator switches sessions
- **WHEN** a different session is selected
- **THEN** the primary transcript and private goal/context change to that session while container shared context remains visible

#### Scenario: Agent output is shown
- **WHEN** public Agent message events exist for the current run
- **THEN** the UI labels them as Agent output and does not present hidden reasoning or fabricated dialogue
