## ADDED Requirements

### Requirement: Session workspace status reflects provisioning failure
The worker SHALL persist `PROVISIONING` before it waits for a session workspace and SHALL persist `FAILED` with an actionable sanitized workspace error if provisioning fails. It SHALL NOT leave a failed workspace as `PENDING`, `PROVISIONING`, or `READY`.

#### Scenario: Agent-server cannot become healthy
- **WHEN** a session workspace health check times out or reports an unrecoverable startup error
- **THEN** its work session reports `workspace_status` `FAILED` with the corresponding readable error and its run becomes terminally failed
