## MODIFIED Requirements

### Requirement: Trustworthy feedback
The frontend SHALL clearly distinguish loading, empty, success, warning, terminal failure, API failure, partial-data, and persisted execution-startup states and SHALL not present speculative or simulated backend facts as real. For an active Agent Team session, it SHALL show the known queued, workspace-provisioning, workspace-ready/agent-starting, or active-execution stage with accessible text and a recognizable activity indicator. For a recorded startup failure, it SHALL identify the failed stage, show the sanitized persisted error, and stop presenting the session as actively waiting.

#### Scenario: Backend error is shown
- **WHEN** an API action fails
- **THEN** the message identifies the failed action in plain language, preserves recoverable user input or known data, and offers retry when safe

#### Scenario: Agent workspace is provisioning
- **WHEN** an Agent Team session reports persisted workspace provisioning state
- **THEN** the workspace presents a labeled activity indicator and the known preparation stage without fabricating progress or execution completion

#### Scenario: Agent startup failure is recorded
- **WHEN** an Agent Team session reports a failed workspace startup
- **THEN** the workspace displays the persisted actionable error and does not retain a generic planning spinner
