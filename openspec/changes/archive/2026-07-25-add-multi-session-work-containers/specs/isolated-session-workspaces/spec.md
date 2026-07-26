## ADDED Requirements

### Requirement: Optional isolated Git worktree
A work session SHALL allow the operator to choose the normal isolated workspace root or a session-specific Git worktree before the session starts.

#### Scenario: Worktree is enabled
- **WHEN** a session with worktree enabled provisions a valid Git workspace
- **THEN** the worker creates a sanitized session branch and worktree, persists their identifiers and starts the Agent conversation in that worktree directory

#### Scenario: Worktree is disabled
- **WHEN** a session does not request a worktree
- **THEN** the Agent uses the existing isolated workspace root and no worktree is implied in the UI

### Requirement: Fail-closed worktree setup
Worktree setup SHALL fail visibly when Git prerequisites, branch creation or path validation fails and SHALL not silently execute the session in a different directory.

#### Scenario: Worktree cannot be created
- **WHEN** the requested worktree operation fails
- **THEN** the run enters a failed state with an actionable workspace error and the session does not claim worktree readiness

### Requirement: Worktree path safety
Generated branch names and worktree paths SHALL derive only from server-generated identifiers and SHALL remain within the existing workspace boundary.

#### Scenario: Client supplies workspace metadata
- **WHEN** a client attempts to provide a branch name or arbitrary worktree path
- **THEN** the server ignores or rejects those fields and generates safe values itself
