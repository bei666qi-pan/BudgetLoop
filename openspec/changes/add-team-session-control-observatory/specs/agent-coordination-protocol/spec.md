# agent-coordination-protocol Specification

## Purpose

Define the structured coordination contract that every BudgetLoop Agent SHALL follow: role-goal-scoped execution, concise milestone-driven progress signals, explicit blocking declarations, one-round-trip escalation, budget-pressure adaptation, and evidence-backed completion.

## Requirements

### Requirement: Role-Goal-Scoped Execution
An Agent SHALL pursue only the goal assigned to its session role and SHALL NOT initiate work, exploration, or communication outside that role's declared scope.

#### Scenario: Agent achieves its assigned goal
- **WHEN** an Agent's session receives a role goal and all deliverable conditions for that goal are met
- **THEN** the Agent SHALL declare completion with evidence and SHALL NOT continue iterating, exploring adjacent concerns, or volunteering out-of-scope work

#### Scenario: Agent receives an out-of-scope suggestion
- **WHEN** a collaborative message or context suggests work outside the session's role goal
- **THEN** the Agent SHALL acknowledge receipt but SHALL NOT incorporate the out-of-scope work into its execution plan

### Requirement: Short Collaborative Messages to Explicit Recipients
An Agent SHALL send collaborative messages that are concise, addressed to one or more explicit recipient session identities, and limited to the minimum content needed for the intended coordination outcome.

#### Scenario: Agent sends a handoff to a downstream session
- **WHEN** an Agent completes a source-stage deliverable that a downstream session depends on
- **THEN** the handoff message SHALL contain only the conclusion, key evidence, unresolved questions, and the recipient's actionable next step, with explicit `recipient_session_id` set

#### Scenario: Agent sends a clarification question
- **WHEN** an Agent encounters an ambiguity that another session can resolve
- **THEN** the question SHALL be addressed to a specific recipient session, SHALL state the ambiguity in one or two sentences, and SHALL include the sender's current assumption to reduce round-trips

#### Scenario: Agent attempts broadcast or self-addressed message
- **WHEN** an Agent sends a message without an explicit recipient, with itself as the only recipient, or addressed to all sessions in the container
- **THEN** the application layer SHALL reject the message with a constraint violation, and the control-plane audit SHALL record the attempt

### Requirement: Progress Signals Only at Real Milestones
An Agent SHALL emit a structured progress signal only when a concrete milestone is reached, a deliverable item is completed, or the session becomes blocked. An Agent SHALL NOT emit a progress signal solely to report continued activity or tool invocation.

#### Scenario: Agent completes a concrete deliverable
- **WHEN** an Agent finishes an implementation unit, test suite, documentation artifact, or other explicitly planned deliverable
- **THEN** the Agent SHALL emit one progress signal with the updated `milestone`, `completed_items`, and `evidence` fields reflecting the new completion

#### Scenario: Agent runs multiple tool-only iterations without milestone change
- **WHEN** an Agent performs several iterations of tool calls (file reads, searches, edits) that advance work but do not cross a milestone boundary
- **THEN** the Agent SHALL NOT emit any progress signal for those intermediate iterations

#### Scenario: Progress signal missing required structured fields
- **WHEN** an Agent emits a progress signal
- **THEN** the signal SHALL include at minimum the following fields: `summary`, `milestone`, `completed_items`, `next_step`, `blocked`, `blocker_reason` (when blocked), `needs_operator`, and `evidence`, each populated with factual content or an explicit empty/null indicator

### Requirement: Blocking State Declaration with Facts, Attempts, and Needed Actions
When an Agent encounters a condition that prevents forward progress, it SHALL declare the block in its next progress signal with a factual description of the block, a summary of what it has already attempted, and the specific action or input needed to resolve the block.

#### Scenario: Agent is blocked by a missing upstream dependency
- **WHEN** an Agent cannot proceed because a required artifact from another session has not been delivered
- **THEN** the progress signal SHALL set `blocked` to true, SHALL populate `blocker_reason` with the missing dependency identity and what was expected, SHALL list attempted workarounds in `summary`, and SHALL set `needs_operator` to false if the dependency is expected to resolve through normal coordination

#### Scenario: Agent is blocked and requires operator intervention
- **WHEN** an Agent cannot proceed and the resolution requires an operator decision (budget approval, scope change, engine configuration)
- **THEN** the progress signal SHALL set `blocked` to true and SHALL set `needs_operator` to true with `blocker_reason` describing the decision required

#### Scenario: Agent is blocked by a tool or engine error
- **WHEN** an Agent encounters a tool invocation failure, engine error, or environment issue that prevents progress
- **THEN** the progress signal SHALL set `blocked` to true, SHALL include the error category and the failed command/path in `blocker_reason`, SHALL state the number of retry attempts in `summary`, and SHALL set `needs_operator` to true if automatic recovery is exhausted

### Requirement: No Repeated Liveness Reports
An Agent SHALL NOT emit progress signals, messages, or events whose sole purpose is to confirm that the session is still running or that an Agent is still alive. Activity confirmation SHALL be derived from execution events and tool-call records, not from Agent-declared liveness signals.

#### Scenario: Agent has been working without a milestone change for an extended period
- **WHEN** an Agent has been executing tool calls for multiple iterations without reaching a new milestone
- **THEN** the Agent SHALL NOT emit a "still working" or "in progress" message; the observatory SHALL infer liveness from recent `execution_events` timestamps

#### Scenario: Operator queries session status
- **WHEN** an operator views a session in the observatory
- **THEN** the session status and last-activity timestamp SHALL be derived from `execution_events` and `llm_calls`, not from an Agent-emitted heartbeat or status message

### Requirement: Escalation After One Round-Trip Failure
When an Agent-initiated collaborative message (question, handoff, or request) does not receive an acknowledgement from the intended recipient within one complete round-trip (the recipient's next iteration), the sender SHALL escalate by either re-sending the message with an urgency marker to the same recipient, notifying the coordinator session, or flagging `needs_operator` in its next progress signal.

#### Scenario: Message remains unacknowledged after recipient's next iteration
- **WHEN** an Agent sends a question to a specific recipient session AND the recipient completes one full iteration without acknowledging the message
- **THEN** the sending Agent SHALL, in its own following iteration, escalate the unresolved dependency by setting `needs_operator` to true in its next progress signal with `blocker_reason` citing the unacknowledged message identity and the recipient session

#### Scenario: Handoff remains unacknowledged by downstream session
- **WHEN** a handoff message from a completed source stage is not acknowledged by the downstream session after one iteration of that downstream session
- **THEN** the coordinator SHALL be notified via a system-generated audit event, and the team status SHALL reflect an actionable attention state

#### Scenario: Acknowledgement arrives after escalation
- **WHEN** an escalated message is acknowledged after the escalation signal has been emitted
- **THEN** the sending Agent SHALL clear the `needs_operator` flag and `blocked` state in its next progress signal and SHALL continue normal execution

### Requirement: Budget Pressure Adaptation
When the session or team budget pressure transitions to CONSERVATIVE or CRITICAL, the Agent SHALL reduce exploration breadth, reuse existing evidence and prior results where applicable, and prioritize acceptance-oriented completion over exhaustive refinement. When pressure returns to NORMAL, the Agent SHALL resume its standard execution strategy.

#### Scenario: Session enters CONSERVATIVE pressure
- **WHEN** the session's budget consumption rate indicates remaining budget will be exhausted before estimated completion AND the pressure mode transitions to CONSERVATIVE
- **THEN** the Agent SHALL reduce the number of parallel exploration paths, SHALL reuse previously gathered evidence from team shared context or handoffs, and SHALL defer non-critical refinements

#### Scenario: Session enters CRITICAL pressure
- **WHEN** the session's remaining budget is below 15% of allocation or the estimated exhaustion time is under 5 minutes AND the pressure mode transitions to CRITICAL
- **THEN** the Agent SHALL halt all speculative exploration, SHALL select the most complete existing deliverable candidate, SHALL prioritize acceptance-criteria satisfaction over code quality improvements, and SHALL declare completion with whatever evidence has been gathered

#### Scenario: Pressure returns to NORMAL
- **WHEN** the budget is increased or consumption rate drops AND the pressure mode transitions back to NORMAL
- **THEN** the Agent SHALL resume its standard exploration and refinement strategy in the following iteration

### Requirement: Evidence-Backed Completion Declaration
An Agent SHALL NOT declare its role complete without providing concrete, verifiable evidence. The completion declaration SHALL include at minimum: the file paths modified or created, the test commands executed with their pass/fail results, and the shell commands run to verify correctness.

#### Scenario: Agent completes an implementation role
- **WHEN** an Agent determines that all role-goal deliverables are met
- **THEN** the completion progress signal SHALL populate `evidence` with a structured list containing each modified or created file path, the exact test command(s) executed, the test pass/fail tally, and any verification shell command and its result

#### Scenario: Agent completes a testing role
- **WHEN** an Agent determines that all required test coverage has been written and verified
- **THEN** the completion progress signal SHALL populate `evidence` with the test file paths created, the test runner command, the total/passed/failed/skipped counts, and the coverage percentage if the toolchain reports it

#### Scenario: Agent attempts completion without evidence
- **WHEN** an Agent declares completion but the `evidence` field is empty, contains only prose without file/command references, or references files or commands that cannot be verified by the observatory
- **THEN** the observatory SHALL display the completion with a warning indicator and the coordinator SHALL treat the completion as unverified, requiring operator review

#### Scenario: Completion evidence references files outside the session workspace
- **WHEN** an Agent's completion evidence references file paths outside its assigned session workspace
- **THEN** the observatory SHALL flag the evidence as potentially invalid and SHALL not treat those references as verified
