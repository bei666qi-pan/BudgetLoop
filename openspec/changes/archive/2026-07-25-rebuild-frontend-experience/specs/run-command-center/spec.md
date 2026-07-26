## ADDED Requirements

### Requirement: Run state hierarchy
The run route SHALL prioritize run status, current phase/activity, task identity, elapsed or completion context, and the most useful next action ahead of secondary diagnostics.

#### Scenario: Run is active
- **WHEN** a non-terminal run is loaded
- **THEN** the operator can identify what the agent is doing, whether the connection is current, and where to inspect progress without interpreting raw events first

#### Scenario: Run is terminal
- **WHEN** the run reaches a terminal state
- **THEN** the interface stops presenting it as live and offers the final report when available

### Requirement: Budget and pressure supervision
The run route SHALL communicate used, reserved when available, remaining, and limit values for supported budgets and SHALL label normal, conservative, and critical pressure without relying on color alone.

#### Scenario: Budget pressure changes
- **WHEN** the API or event stream reports a new pressure mode
- **THEN** the visible budget summary updates its label and explanatory treatment while retaining the underlying numeric values

#### Scenario: Budget data is partial
- **WHEN** one or more optional budget values are absent
- **THEN** the interface labels the unavailable values and does not replace them with fabricated zeroes

### Requirement: Progressive diagnostic access
The run route SHALL retain access to the event timeline, budget breakdown, reallocations, LLM calls, and supporting run metadata while organizing them below or alongside the primary operational summary.

#### Scenario: Operator inspects detailed activity
- **WHEN** the operator selects a diagnostic area
- **THEN** the relevant real API data is displayed with readable labels, overflow-safe layouts, and clear empty states

### Requirement: Interruptive approval handling
The run route SHALL present pending approval requests prominently, explain the requested action and risk data provided by the API, and support approve, reject, or modify actions through the existing endpoint.

#### Scenario: Approval request arrives
- **WHEN** an approval event with a usable approval identifier is received
- **THEN** the operator is notified without the request being hidden behind secondary diagnostics

#### Scenario: Approval action fails
- **WHEN** an approval response request fails
- **THEN** the request remains actionable and the interface shows an error without claiming that the run resumed

### Requirement: Resilient live updates
The run route SHALL distinguish initial loading, live streaming or refresh, connection degradation, API error, and stale or partial data without inventing progress.

#### Scenario: Live connection is disrupted
- **WHEN** the event connection cannot deliver new data
- **THEN** the existing known run data remains visible and the operator receives a clear connection/retry indication
