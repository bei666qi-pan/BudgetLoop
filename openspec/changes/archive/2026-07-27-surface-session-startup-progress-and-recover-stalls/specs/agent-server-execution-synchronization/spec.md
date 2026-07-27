## ADDED Requirements

### Requirement: Agent-server workspace startup failures converge
BudgetLoop SHALL bound OpenHands agent-server workspace health polling and SHALL fail the run when the published health endpoint does not become healthy. It SHALL preserve a sanitized diagnosis that identifies workspace startup as the failed stage, release any created workspace resources, and SHALL NOT continue into conversation creation or execution.

#### Scenario: Published agent-server health endpoint remains unavailable
- **WHEN** a newly provisioned agent-server workspace repeatedly returns a transport error or non-success health response through the configured startup timeout
- **THEN** the worker marks the run failed with a sanitized workspace startup error, removes the failed workspace container, and does not leave the run in `PLANNING`

#### Scenario: Workspace health endpoint succeeds
- **WHEN** the agent-server health endpoint returns success before the startup timeout
- **THEN** the worker proceeds to initialize the configured workspace and create the conversation normally
