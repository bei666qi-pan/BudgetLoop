# team-session-collaboration Delta Specification

## Purpose

Extend the existing session collaboration spec with message type/idempotency/acknowledgment fields, a full message state machine (queued → injected → acknowledged/failed), CLI safety checkpoint injection semantics, anti-runaway delivery controls, and handoff content constraints that prohibit hidden reasoning exposure.

## MODIFIED Requirements

### Requirement: Explicit cross-session message
The system SHALL allow an operator or another session identity in the same container to send a typed, idempotent message or handoff to one recipient session with immutable provenance, delivery state, and acknowledgment tracking. Handoff content SHALL be constrained to conclusions, evidence, open questions, and next steps only.

#### Scenario: Handoff is queued
- **WHEN** a sender selects a different session in the same container and submits non-empty handoff content containing only conclusions, evidence, open questions, and next steps
- **THEN** one queued message is stored with sender, recipient, message_type, content, idempotency_key, and creation time, with delivery state `queued`

#### Scenario: Cross-container recipient is attempted
- **WHEN** the sender or recipient does not belong to the owning container
- **THEN** the message is rejected and no content crosses the container boundary

#### Scenario: Self-send is attempted
- **WHEN** a sender attempts to send a message where sender_session_id equals recipient_session_id
- **THEN** the message is rejected with an explicit error indicating self-send is prohibited

#### Scenario: Idempotent message resubmission
- **WHEN** the same idempotency_key is submitted again for a message
- **THEN** the existing message with its current state is returned without creating a duplicate, and the idempotency_key unique constraint prevents duplicate rows

#### Scenario: Handoff contains hidden reasoning
- **WHEN** handoff content includes internal reasoning, private context, credentials, or intermediate chain-of-thought from another session
- **THEN** the message is rejected or the content is stripped such that only conclusions, evidence, open questions, and next steps are transmitted

### Requirement: Controlled Agent inbox delivery
The worker SHALL enqueue recipient messages for the next Agent iteration, inject them at the appropriate safety checkpoint, enforce anti-runaway limits before injection, and transition messages through the states queued → injected → acknowledged (or failed). Messages SHALL be injected at a safety checkpoint before each iteration begins, and the worker SHALL mark them `injected` only after the checkpoint passes. The worker SHALL mark them `acknowledged` only after the Agent confirms receipt via a `send_message` tool call. If the Agent fails to acknowledge after the configured retry limit or the session terminates, the message SHALL be marked `failed`.

#### Scenario: Recipient begins the next iteration and injection succeeds
- **WHEN** one or more queued messages exist for the session's current run and the safety checkpoint passes anti-runaway rate, count, and token limit checks
- **THEN** their explicit content and provenance are appended to the iteration instruction, delivery state is set to `injected`, and an injection event is recorded

#### Scenario: Agent acknowledges receipt
- **WHEN** the Agent calls the `send_message` tool confirming receipt of the injected message
- **THEN** the message delivery state transitions to `acknowledged`, `acknowledged_at` is set to the current timestamp, and the acknowledgment is recorded

#### Scenario: Agent message request fails
- **WHEN** the worker cannot submit the iteration message containing the injected messages
- **THEN** inbox messages remain in `injected` state and are retried at the next safety checkpoint; after the configured retry limit (3 attempts) without acknowledgment, the message delivery state transitions to `failed`

#### Scenario: Message fails after retry exhaustion
- **WHEN** a message has been injected 3 times but the Agent has not acknowledged receipt, or the session terminates before acknowledgment
- **THEN** the message delivery state transitions to `failed`, a `message_failed` event is emitted, and no further injection is attempted for that message

#### Scenario: Anti-runaway limit reached—rate cap
- **WHEN** the container has already dispatched the configured maximum number of automatic messages within the current time window (default 30 messages per minute)
- **THEN** remaining queued messages are not injected, automatic replies are paused, a `team_control_audit` event is emitted, and the operator is notified

#### Scenario: Anti-runaway limit reached—reply rounds cap
- **WHEN** any session in the container has participated in the configured maximum number of automatic reply rounds (default 5 rounds)
- **THEN** automatic replies for that session are paused, a `team_control_audit` event is emitted, and the operator is notified

#### Scenario: Anti-runaway limit reached—inbox token cap
- **WHEN** the cumulative token count of queued inbox messages for a session exceeds the configured percentage of the session's current remaining budget (default 5%)
- **THEN** no additional messages are injected into that session's inbox, a `budget_pressure_change` event is emitted with pressure level CRITICAL, and the operator is notified

#### Scenario: Broadcast N×N reply is attempted
- **WHEN** a message is submitted without an explicit single recipient (i.e., broadcast or multi-recipient)
- **THEN** the message is rejected and the sender is informed that explicit single-recipient addressing is required

#### Scenario: CLI engine receives injection at safety checkpoint
- **WHEN** the worker is using a CLI engine adapter (Codex, Gemini CLI, OpenCode) that does not support hot injection, and a queued message exists
- **THEN** the message is injected at the beginning of the next iteration's safety checkpoint, delivery state is set to `injected`, and the frontend displays "waiting for next execution checkpoint" until the message transitions to `acknowledged` or `failed`

## ADDED Requirements

### Requirement: Message state machine and lifecycle
A session message SHALL progress through a defined state machine: `queued` → `injected` → `acknowledged` or `failed`. Each state transition SHALL be recorded atomically in the `session_messages` row within the same database transaction as the triggering event. The state machine SHALL be enforced at the control plane in PostgreSQL, not in Agent prompt logic.

#### Scenario: Normal lifecycle
- **WHEN** a message is created, injected at a safety checkpoint, and acknowledged by the recipient Agent
- **THEN** the message transitions queued → injected → acknowledged with timestamps recorded at each transition

#### Scenario: Failure lifecycle
- **WHEN** a message is injected but the Agent fails to acknowledge after the retry limit or the session is terminated
- **THEN** the message transitions queued → injected → failed and no further state changes are possible

#### Scenario: State transition atomicity
- **WHEN** a worker updates a message's delivery state
- **THEN** the state change, any associated execution event, and any audit event are committed in the same transaction

### Requirement: CLI safety checkpoint injection
For CLI-based engines that do not support runtime hot message injection, the worker SHALL inject queued messages at a safety checkpoint before each Agent iteration begins and SHALL update the delivery state to `injected` at that point. The frontend SHALL display an honest delivery status that distinguishes server-engine real-time injection from CLI-engine checkpoint-bound injection. The worker SHALL NOT fabricate real-time delivery semantics for CLI engines.

#### Scenario: CLI engine checkpoint injection
- **WHEN** a CLI engine adapter processes the next iteration for a session with queued messages
- **THEN** the `check_injection_point()` method retrieves all queued messages, sets their delivery state to `injected`, and appends their content to the iteration instruction before the engine call begins

#### Scenario: Frontend displays honest CLI delivery status
- **WHEN** a message is in `queued` or `injected` state for a CLI engine session
- **THEN** the frontend displays "waiting for next execution checkpoint" instead of "delivered" or "acknowledged"

#### Scenario: CLI engine acknowledgment
- **WHEN** a CLI engine Agent outputs a structured progress signal or acknowledgment in its `iteration_complete` event via `extract_progress_signal()`
- **THEN** the adapter transitions the corresponding message to `acknowledged` and sets `acknowledged_at`

### Requirement: Anti-runaway delivery controls
The control plane SHALL enforce hard limits on cross-session message delivery to prevent runaway inter-Agent communication loops: per-container message rate cap, per-session automatic reply round cap, per-session inbox token cap, prohibition of self-send, prohibition of cross-container delivery, and requirement for explicit single recipients. When any limit is reached, automatic replies SHALL be paused for the affected scope, an audit event SHALL be recorded, and the operator SHALL be notified through the team SSE stream.

#### Scenario: Rate cap enforced atomically
- **WHEN** the container's message dispatch counter exceeds the configured per-minute limit (default 30)
- **THEN** no additional messages are injected for the remainder of the time window, and the limit reset is managed by a TTL-based counter

#### Scenario: Reply round cap enforced per session
- **WHEN** a session has participated in the configured maximum automatic reply rounds (default 5)
- **THEN** the session's automatic reply capability is suspended, and only operator-initiated messages are accepted for that session

#### Scenario: Inbox token cap enforced before injection
- **WHEN** the cumulative token count of a session's queued inbox exceeds 5% of its remaining budget
- **THEN** no additional messages are injected, budget pressure is set to CRITICAL, and the operator is notified via SSE

#### Scenario: Self-send prohibited at application layer
- **WHEN** sender_session_id equals recipient_session_id
- **THEN** the message is rejected before any database write occurs

#### Scenario: Cross-container delivery prohibited
- **WHEN** sender and recipient do not share the same container_id
- **THEN** the message is rejected with no content crossing the container boundary

#### Scenario: Broadcast without explicit recipient prohibited
- **WHEN** a message is submitted with null, empty, or multiple recipients
- **THEN** the message is rejected and the sender receives an error indicating single-recipient addressing is required

#### Scenario: Limit breach produces audit event
- **WHEN** any anti-runaway limit is reached
- **THEN** a `team_control_audit` event is written to `team_audit_events` with the action, scope, and limit details, and the event is emitted on the team SSE stream

### Requirement: Handoff content constraints
Handoff messages between sessions SHALL contain only conclusions, evidence, open questions, and next steps. The system SHALL NOT transmit hidden reasoning, internal chain-of-thought, private context from the sender session, credentials, API keys, or any content that would reveal the sender's internal deliberation. Validation SHALL be performed at the control plane before the message is stored.

#### Scenario: Valid handoff content accepted
- **WHEN** a handoff message contains only conclusions, evidence, open questions, and next steps
- **THEN** the message is stored and delivered normally

#### Scenario: Credential-bearing handoff rejected
- **WHEN** a handoff message contains credentials, API keys, tokens, or other secrets
- **THEN** the message is rejected before storage

#### Scenario: Internal reasoning stripped from handoff
- **WHEN** a handoff message contains internal reasoning, intermediate step-by-step logic, or raw chain-of-thought from the sender Agent
- **THEN** the reasoning content is stripped, and only the structural fields (conclusions, evidence, open questions, next steps) are transmitted

#### Scenario: Private context not leaked across sessions
- **WHEN** a handoff message is delivered to the recipient session
- **THEN** the recipient's transcript SHALL NOT contain the sender's private_context, internal reasoning, or any data from the sender's non-public execution events
