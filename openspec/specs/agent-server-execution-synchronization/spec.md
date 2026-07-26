# agent-server-execution-synchronization Specification

## Purpose
TBD - created by archiving change wait-for-agent-server-execution-start. Update Purpose after archive.
## Requirements
### Requirement: Server execution is scheduled explicitly
BudgetLoop SHALL submit each OpenHands agent-server iteration without implicit execution and SHALL then invoke the conversation run endpoint exactly once before waiting for completion. CLI execution engines SHALL retain their single-call run behavior and SHALL NOT receive a separate conversation run call.

#### Scenario: Server iteration starts through the run endpoint
- **WHEN** BudgetLoop drives an iteration through the OpenHands server transport
- **THEN** it sends the instruction with `run=false`, invokes `POST /api/conversations/{id}/run` exactly once, and then waits for execution-start evidence

#### Scenario: CLI iteration executes directly
- **WHEN** BudgetLoop drives an iteration through a CLI transport
- **THEN** it sends the instruction with `run=true` and does not invoke a separate conversation run method

#### Scenario: Explicit run scheduling fails
- **WHEN** the instruction event is accepted but the server run endpoint fails
- **THEN** BudgetLoop propagates the sanitized execution error, releases the outstanding budget reservation, and leaves queued collaboration messages undelivered for retry

#### Scenario: Conversation is already running
- **WHEN** the explicit conversation run endpoint returns 409 because OpenHands already started the submitted message
- **THEN** BudgetLoop treats that endpoint-specific conflict as idempotent scheduling success and waits for the running conversation instead of failing the task

### Requirement: Pre-start idle is not execution completion
BudgetLoop SHALL NOT treat an agent-server conversation's initial plain `idle` or usage-free `finished` state as completion of a newly scheduled run. It SHALL wait for execution-start evidence, an unambiguous failure/pause result, or completed usage evidence before settling the iteration.

#### Scenario: OpenHands reports idle before running
- **WHEN** an explicitly scheduled run is accepted and the first conversation poll returns idle before a later poll returns running
- **THEN** BudgetLoop continues waiting and does not settle budget, run tests, or advance the task phase from the initial idle response

#### Scenario: OpenHands reports stale finished before running
- **WHEN** a run request succeeds but the first conversation poll returns `finished` with no completed usage before a later poll returns running
- **THEN** BudgetLoop continues waiting and does not treat the stale finished state as execution completion

#### Scenario: Execution completes between polls
- **WHEN** the first observed post-message state is idle but the conversation contains at least one completed token-usage record
- **THEN** BudgetLoop accepts the execution as completed and records its real usage

#### Scenario: Ancillary metrics exist without token usage
- **WHEN** the conversation reports latency or cost placeholders but contains no token-usage record, agent event, or running observation
- **THEN** BudgetLoop continues waiting and does not settle the iteration as a completed LLM execution

#### Scenario: Non-idle terminal state is returned immediately
- **WHEN** OpenHands fails, pauses, becomes stuck, or requests confirmation before the first poll
- **THEN** BudgetLoop returns that unambiguous terminal state without waiting for a running observation

### Requirement: Never-started execution fails within a bound
BudgetLoop SHALL fail a newly scheduled agent-server iteration with a sanitized synchronization error when no execution-start or completion evidence appears within the startup timeout. It SHALL release the outstanding budget reservation and SHALL NOT consume repeated task iterations for the same never-started message.

#### Scenario: Conversation remains idle
- **WHEN** OpenHands accepts an explicit run request but remains plain idle with no usage evidence through the startup timeout
- **THEN** the run fails once with an actionable agent-server synchronization error and does not exhaust the configured LLM-call budget through empty iterations

### Requirement: Managed OpenHands model uses the OpenAI-compatible provider
BudgetLoop SHALL qualify the model passed to OpenHands server transport with LiteLLM's `openai/` provider because the managed runtime implements the OpenAI-compatible protocol. It SHALL NOT change the user-configured gateway model, capability claim, or generated-application model value.

#### Scenario: Bare custom gateway model starts in OpenHands
- **WHEN** the managed runtime model is `deepseek-v4-pro-202606`
- **THEN** the OpenHands conversation is configured with `openai/deepseek-v4-pro-202606` while the managed runtime forwards the original model name to the configured gateway

### Requirement: Agent-server execution errors fail fast
BudgetLoop SHALL fail the current run when OpenHands reports execution status `error` or `stuck`. It SHALL release the outstanding reservation and SHALL NOT run tests, settle a successful call, or consume another loop iteration for that failed execution.

#### Scenario: LiteLLM rejects conversation model configuration
- **WHEN** OpenHands reports `error` before producing agent events or token usage
- **THEN** BudgetLoop transitions the run to failed after the first attempt and preserves a sanitized error status for diagnosis

### Requirement: OpenHands metrics are normalized without leaking reservations
BudgetLoop SHALL support response-scoped object records and legacy numeric records in OpenHands latency and cost metrics. It SHALL correlate object records by response ID where available. If observation normalization or persistence fails, it SHALL roll back uncommitted observation data and release the outstanding iteration reservation.

#### Scenario: Latency is a response-scoped object
- **WHEN** OpenHands reports a token usage with a response ID and a latency record containing the same response ID plus a numeric `latency` field
- **THEN** BudgetLoop records the corresponding LLM call duration in milliseconds without raising a type conversion error

#### Scenario: Observation processing fails after execution
- **WHEN** the agent execution completed but metric normalization or observation persistence raises before settlement commits
- **THEN** BudgetLoop rolls back the partial observation unit, releases the iteration reservation, and fails the run without leaving reserved calls or tokens stranded

### Requirement: OpenHands coding conversations receive official workspace tools
BudgetLoop SHALL configure OpenHands server-transport conversations with OpenHands' own terminal, file-editor, and task-tracker tools. It SHALL continue to rely on the selected workspace access mode and OpenHands executors rather than implementing separate BudgetLoop file or shell tools.

#### Scenario: Full-access coding task can modify and verify a project
- **WHEN** BudgetLoop creates an OpenHands conversation for a full-access coding task
- **THEN** the agent request includes OpenHands' registered `terminal`, `file_editor`, and `task_tracker` tools, allowing the agent to inspect the mounted project, edit files, and run the requested test command
