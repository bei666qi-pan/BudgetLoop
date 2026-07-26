## ADDED Requirements

### Requirement: Agent execution respects the server-side secret boundary
The system SHALL keep gateway and upstream credentials in the control plane when configuring any agent-server execution. It SHALL use a scoped managed-runtime capability for the agent-server's model invocation and SHALL NOT write either credential class to a project file, database business record, browser payload, or log.

#### Scenario: Agent-server conversation is configured
- **WHEN** the worker creates an OpenHands agent-server conversation for a task run
- **THEN** its LLM configuration contains only the managed proxy URL, model alias, and run-scoped capability, never the configured upstream API key

#### Scenario: Runtime configuration is rejected
- **WHEN** the workspace cannot obtain a valid scoped capability
- **THEN** the worker does not substitute the upstream credential and exposes only a stable sanitized failure reason
