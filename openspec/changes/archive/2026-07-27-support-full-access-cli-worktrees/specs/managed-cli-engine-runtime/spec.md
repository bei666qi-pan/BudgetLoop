## ADDED Requirements

### Requirement: CLI engines remain isolated from direct host-folder access
Managed CLI engines SHALL run only in their worker-local isolated workspaces and SHALL not be selected for a full-access Agent Team.

#### Scenario: Guided setup selects direct project access
- **WHEN** an operator enables direct project access for a guided Agent Team
- **THEN** the setup selects the supported server engine and does not offer CLI engines for that mode

#### Scenario: API receives a full-access CLI request
- **WHEN** a client submits a full-access Agent Team using a CLI engine
- **THEN** the API rejects the request before creating a container, task, run, or workspace
