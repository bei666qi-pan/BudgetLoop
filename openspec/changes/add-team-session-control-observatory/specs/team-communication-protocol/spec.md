# team-communication-protocol Specification

## Purpose

Define the team communication protocol with a PostgreSQL-enforced message state machine, idempotent delivery, anti-runaway guardrails, CLI safety-checkpoint injection with honest status, and handoff content restrictions that prevent hidden reasoning from crossing session boundaries.

## ADDED Requirements

### Requirement: Classified message types
Each message sent between operators and sessions or between sessions SHALL carry a `message_type` value of `message`, `handoff`, `progress_update`, or `system_fact` that determines its rendering, delivery priority, and anti-runaway quota treatment.

#### Scenario: Operator sends a general message
- **WHEN** an operator submits content without designating it as a handoff, progress update, or system fact
- **THEN** the message is stored with `message_type = 'message'` and displayed as a standard chat entry

#### Scenario: Session sends a handoff
- **WHEN** an Agent sends structured output containing `conclusion`, `evidence`, `open_questions`, and `next_step` to a downstream role
- **THEN** the system stores the message with `message_type = 'handoff'` and renders it with handoff formatting distinct from general messages

#### Scenario: Agent publishes a progress signal
- **WHEN** an Agent declares a milestone or progress update via structured output
- **THEN** the system stores a message with `message_type = 'progress_update'` and also records a `session_progress_signals` row, maintaining a single source of truth per milestone

#### Scenario: System posts a budget or state fact
- **WHEN** the system publishes a team-wide notification such as budget-pressure change, container pause, or anti-runaway limit reached
- **THEN** the message is stored with `message_type = 'system_fact'`, attributed to a system sender identity, and is visible to all sessions in the container

#### Scenario: Invalid message_type is submitted
- **WHEN** a message creation request includes a `message_type` outside the allowed enumeration
- **THEN** the server rejects the request with HTTP 422 and the message is not stored

### Requirement: Idempotent message submission
Every message submission SHALL accept an optional `idempotency_key`. When a duplicate `idempotency_key` is submitted, the system MUST return the already-stored message without creating a second row, and the PostgreSQL unique partial index SHALL be the authoritative enforcement mechanism.

#### Scenario: First submission with idempotency_key
- **WHEN** a message is submitted with a novel `idempotency_key`
- **THEN** the message is stored and returned with HTTP 201

#### Scenario: Duplicate idempotency_key is retried
- **WHEN** an identical `idempotency_key` is submitted again for the same container
- **THEN** the existing message record is returned with HTTP 200, no new row is inserted, and the delivery status is not altered

#### Scenario: idempotency_key not provided
- **WHEN** a message is submitted without an `idempotency_key`
- **THEN** the message is always stored as a new row and a server-generated UUID is recorded as the message identifier

#### Scenario: idempotency_key collision across containers
- **WHEN** the same `idempotency_key` is used in two different containers
- **THEN** each container stores its own independent message row because the uniqueness constraint is scoped per container

### Requirement: Message state machine in PostgreSQL
Every message SHALL transition through a PostgreSQL-enforced state machine with exactly four states: `queued`, `injected`, `acknowledged`, and `failed`. All state transitions MUST be executed via SQL UPDATE within the worker transaction, and no state SHALL be stored outside PostgreSQL.

#### Scenario: Message is created
- **WHEN** a message is first stored
- **THEN** its `status` is `queued` and `acknowledged_at` is NULL

#### Scenario: Worker injects message into Agent iteration
- **WHEN** the worker detects a queued message for the current run at a safety checkpoint and appends it to the next iteration instruction
- **THEN** the message `status` transitions to `injected` atomically within the same worker transaction, and a `delivery_event` is recorded

#### Scenario: Agent acknowledges receipt
- **WHEN** the Agent performs a successful `send_message` tool call or a structured output that explicitly confirms the message was received
- **THEN** the message `status` transitions to `acknowledged`, `acknowledged_at` is set to the current timestamp, and no further delivery attempts are made for this message

#### Scenario: Injection fails with recoverable error
- **WHEN** the worker cannot append the message to the iteration instruction due to a transient error (e.g., LLM API timeout)
- **THEN** the message remains `queued` and is retried at the next safety checkpoint, up to a maximum of 3 injection attempts

#### Scenario: Injection fails permanently
- **WHEN** the message fails injection 3 times, the Agent returns an unrecoverable error, or the target session enters a terminal state (COMPLETED/FAILED/CANCELLED)
- **THEN** the message `status` transitions to `failed` and the failure reason is recorded in a `delivery_event`

#### Scenario: Duplicate state transition attempted
- **WHEN** a state transition attempts to move a message from `failed` back to `queued` or from `acknowledged` to `injected`
- **THEN** the transition is rejected because it violates the allowed state graph

### Requirement: CLI engine safety-checkpoint injection with honest status
When the target session runs on a CLI engine (Codex, Gemini CLI, OpenCode) that does not support runtime hot-injection, the message SHALL be injected at the next safety checkpoint—the boundary between consecutive Agent iterations—and the frontend MUST display "等待下次执行检查点" (waiting for next execution checkpoint) while the status is `queued` or `injected` for CLI sessions, never claiming real-time delivery.

#### Scenario: CLI session has a queued message
- **WHEN** a message's recipient session uses a CLI engine and the message status is `queued`
- **THEN** the frontend displays the status label as "等待下次执行检查点" and does not show "已送达" (delivered)

#### Scenario: CLI worker reaches a safety checkpoint
- **WHEN** the CLI engine's worker begins the next iteration and detects queued messages for the session
- **THEN** the messages are injected into the next iteration instruction, their status transitions to `injected`, and the frontend continues to display "等待 Agent 确认" (waiting for Agent confirmation)

#### Scenario: CLI Agent acknowledges via structured output
- **WHEN** the CLI Agent returns from the iteration with structured output that includes a message acknowledgement and the worker extracts it via `extract_progress_signal()`
- **THEN** the message status transitions to `acknowledged` and the frontend displays "已确认" (acknowledged)

#### Scenario: Server engine session has a queued message
- **WHEN** a message's recipient session uses a server-based engine that supports hot-injection
- **THEN** the frontend distinguishes the engine type and may display faster status transitions, but the same `queued → injected → acknowledged` state machine applies

#### Scenario: CLI session terminates before message injection
- **WHEN** the target CLI session reaches a terminal state before the next safety checkpoint
- **THEN** the message status transitions to `failed` with the reason "session-terminated-before-injection"

### Requirement: Handoff content restricted to conclusion, evidence, open questions, and next step
Every `handoff` message SHALL contain only the fields `conclusion`, `evidence`, `open_questions`, and `next_step`. No hidden reasoning, credential, internal monologue, or `private_context` from the source session SHALL be included in a handoff payload. The system MUST validate handoff content at storage time.

#### Scenario: Valid handoff is stored
- **WHEN** a handoff message is submitted with only the permitted fields (`conclusion`, `evidence`, `open_questions`, `next_step`)
- **THEN** the message is stored and delivered normally

#### Scenario: Handoff contains disallowed fields
- **WHEN** a handoff message attempts to include fields such as `hidden_reasoning`, `internal_notes`, `private_context`, `credentials`, or any field not in the permitted set
- **THEN** the server strips disallowed fields or rejects the message with HTTP 422, and the disallowed content is never persisted

#### Scenario: Handoff content is rendered to recipient
- **WHEN** the recipient session receives a handoff in its inbox
- **THEN** only `conclusion`, `evidence`, `open_questions`, and `next_step` are visible; no hidden reasoning from the source session appears in the inbox or transcript

#### Scenario: Operator inspects a delivered handoff
- **WHEN** an operator views a handoff in the team chat or session transcript
- **THEN** the handoff is labeled with its message type, sender, recipient, and timestamp, and the operator sees only the permitted fields

### Requirement: Sender-recipient validation at application layer
The system SHALL validate at message submission time that the sender and recipient are distinct sessions in the same container. Self-send, cross-container delivery, and messages to terminal sessions MUST be rejected.

#### Scenario: Self-send is attempted
- **WHEN** `sender_session_id` equals `recipient_session_id`
- **THEN** the server rejects the request with HTTP 422 and the reason "cannot-send-to-self"

#### Scenario: Cross-container delivery is attempted
- **WHEN** the sender or recipient session does not belong to the owning container
- **THEN** the server rejects the request with HTTP 422 and the reason "cross-container-delivery-forbidden"

#### Scenario: Recipient session is in a terminal state
- **WHEN** the recipient session has a status of COMPLETED, FAILED, or CANCELLED
- **THEN** the server rejects the request with HTTP 422 and the reason "recipient-session-terminal"

#### Scenario: Operator sends to a valid active session
- **WHEN** an operator (sender is null or an operator identity) sends a message to an active session in the same container
- **THEN** the message is accepted and stored with `sender_session_id` set to NULL indicating operator origin

### Requirement: Anti-runaway hard limits enforced in control plane
The control plane SHALL enforce hard rate limits on team communication—including per-container messages per minute, per-session auto-reply rounds, and inbox cumulative token ceiling—independent of Agent prompt-based behavior constraints. When any limit is reached, auto-reply SHALL be suspended, an audit event SHALL be recorded, and the operator SHALL be notified.

#### Scenario: Container message rate limit is hit
- **WHEN** the number of new messages created in a single container exceeds the configured per-minute limit (default: 30)
- **THEN** the server rejects further message creation with HTTP 429, auto-reply is paused for that container, a `team_audit_events` row is written with action `anti-runaway-rate-limit-hit`, and the frontend displays a warning banner

#### Scenario: Session auto-reply round limit is hit
- **WHEN** a single session has automatically replied to messages for the configured round limit (default: 5 rounds) within the current run
- **THEN** the worker stops injecting auto-reply messages for that session, records a `team_audit_events` row with action `anti-runaway-round-limit-hit`, and requests operator intervention

#### Scenario: Inbox token ceiling is exceeded
- **WHEN** the cumulative token count of queued and injected messages in a recipient's inbox exceeds the configured percentage of the session's remaining budget (default: 5%)
- **THEN** new messages to that recipient are rejected with HTTP 429, existing queued messages remain but no new injections occur, and the operator is notified with the session's current inbox token count vs. limit

#### Scenario: Broadcast-style N×N reply is attempted
- **WHEN** a message is submitted without an explicit, singular `recipient_session_id` (i.e., attempting to send to all sessions or multiple recipients)
- **THEN** the server rejects the request with HTTP 422 and the reason "explicit-recipient-required"

#### Scenario: Operator resumes auto-reply after limit
- **WHEN** the operator explicitly resumes auto-reply for a container or session that hit an anti-runaway limit
- **THEN** the limit counters are reset, auto-reply is re-enabled, and a `team_audit_events` row is written with action `anti-runaway-resumed-by-operator`

### Requirement: Acknowledgement only by genuine Agent confirmation
The `acknowledged` status SHALL be set exclusively when the Agent explicitly confirms receipt of a specific message via a `send_message` tool call or a structured `acknowledge` output. The worker MUST verify the confirmed message ID exists and belongs to the acknowledging session before performing the state transition.

#### Scenario: Agent confirms a specific message
- **WHEN** the Agent calls `send_message` with an `acknowledging_message_id` that matches a queued or injected message for its session
- **THEN** that message's status transitions to `acknowledged` with the current timestamp

#### Scenario: Agent acknowledges a non-existent message
- **WHEN** the Agent's `acknowledging_message_id` does not match any queued or injected message for its session
- **THEN** the acknowledgement is logged as a warning but no state transition is performed

#### Scenario: Agent acknowledges another session's message
- **WHEN** the Agent's `acknowledging_message_id` matches a message whose recipient is a different session
- **THEN** the acknowledgement is rejected and the worker logs a potential misbehavior event

#### Scenario: Agent fails to acknowledge within timeout
- **WHEN** a message has been `injected` for the configured timeout period (default: 3 iterations or 10 minutes) without acknowledgement
- **THEN** the message status transitions to `failed` with the reason "acknowledgement-timeout"

### Requirement: Delivery status truthfully displayed to operator
The frontend SHALL render the exact database status of each message with engine-aware labels—"已排队" for queued, "等待下次执行检查点" for CLI injected, "已送达" for server-injected, "已确认" for acknowledged, and "送达失败" for failed—and SHALL NOT fabricate or assume delivery states.

#### Scenario: Message is queued for a server-engine session
- **WHEN** a message has status `queued` and the recipient uses a server-based engine
- **THEN** the frontend displays "已排队" with a spinner icon

#### Scenario: Message is injected for a CLI-engine session
- **WHEN** a message has status `injected` and the recipient uses a CLI engine
- **THEN** the frontend displays "等待 Agent 确认" with an hourglass icon

#### Scenario: Message is acknowledged
- **WHEN** a message has status `acknowledged`
- **THEN** the frontend displays "已确认" with a checkmark icon and the `acknowledged_at` timestamp

#### Scenario: Message has failed
- **WHEN** a message has status `failed`
- **THEN** the frontend displays "送达失败" with an error icon and the failure reason in a tooltip

#### Scenario: SSE reconnection recovers correct statuses
- **WHEN** the frontend reconnects via SSE after a disconnection and replays events via `Last-Event-ID`
- **THEN** all message status labels reflect the latest database state, not a stale client-side cache

### Requirement: Audit trail for all message state transitions
Every message state transition SHALL be recorded as a delivery event with the old status, new status, timestamp, and triggering context. All control-plane anti-runaway interventions SHALL additionally be written to `team_audit_events`.

#### Scenario: Message transitions from queued to injected
- **WHEN** the worker injects a message
- **THEN** a delivery event is recorded with `event_type = 'message_injected'`, `old_status = 'queued'`, `new_status = 'injected'`, and the iteration number

#### Scenario: Anti-runaway limit triggers suspension
- **WHEN** the container message rate limit or session round limit is reached
- **THEN** a `team_audit_events` row is written with `action` set to the specific limit type, `container_id`, `session_id`, and the threshold value

#### Scenario: Operator queries audit trail
- **WHEN** an operator retrieves the audit events for a container
- **THEN** all message state transitions and anti-runaway interventions are returned in chronological order, attributable to the triggering session or operator

### Requirement: Database as sole source of truth for message state
PostgreSQL SHALL be the exclusive store for message state, status, delivery events, and audit records. No message state SHALL be held exclusively in application memory, Redis, or frontend cache without a corresponding durable database row.

#### Scenario: Worker restarts after crash
- **WHEN** the worker process restarts after an ungraceful termination
- **THEN** all message states are recovered from PostgreSQL; no queued, injected, or unacknowledged messages are lost or silently dropped

#### Scenario: Concurrent state transitions on the same message
- **WHEN** two workers attempt to transition the same message concurrently (e.g., injection and acknowledgement race)
- **THEN** PostgreSQL row-level locking or optimistic concurrency via `status` check ensures exactly one transition succeeds and the other is rejected with no duplicate events

#### Scenario: Message status query returns authoritative state
- **WHEN** the frontend or API queries a message's status
- **THEN** the returned value is read directly from the `session_messages` row in PostgreSQL, never from an in-memory cache that could be stale
