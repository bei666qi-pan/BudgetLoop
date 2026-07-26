# isolated-session-workspaces Specification

## Purpose

Define optional session-specific Git worktrees with server-controlled naming, workspace-bound paths and fail-closed execution behavior.

## Requirements

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

### Requirement: Explicit selected-folder authorization for teams
An Agent Team SHALL default to isolated workspaces and SHALL use a host project folder only when the operator explicitly selects full access, supplies a validated canonical path, acknowledges direct writes, and confirms the final setup.

#### Scenario: Prompt mentions a local path
- **WHEN** a conversational task description contains a filesystem path but the operator has not selected full access through the permission control
- **THEN** the team remains isolated and the path is not mounted, persisted as authorization, or treated as consent

#### Scenario: Native folder picker is used
- **WHEN** the operator invokes the macOS folder chooser and accepts a folder
- **THEN** the returned path populates the permission control for review but grants no execution access until final confirmation

### Requirement: Full-access team worktree isolation
Every enabled session in a full-access preset team SHALL operate in a unique server-generated Git worktree derived from its session identifier and SHALL never execute concurrently in the selected repository root.

#### Scenario: Full-access sessions provision successfully
- **WHEN** confirmed team runs provision the writable host project
- **THEN** each session receives a unique branch and worktree below the controlled workspace location and its Agent conversation starts in that worktree

#### Scenario: Worktree cannot be honored
- **WHEN** mount, Git initialization, branch creation, or worktree validation fails for a requested full-access session
- **THEN** that run fails visibly with an actionable workspace error and does not fall back to a shared folder or isolated copy

### Requirement: One folder policy and one enforcer
The API SHALL persist the declarative folder policy and canonical path in run configuration, and the workspace manager SHALL remain the single translation point from that policy to Docker mounts and worktree directories.

#### Scenario: Worker receives persisted full access
- **WHEN** a worker provisions a run whose model configuration contains confirmed full access
- **THEN** it mounts only the validated selected project as the writable workspace and applies the requested server-owned worktree policy

#### Scenario: Persisted policy is invalid
- **WHEN** a worker encounters a missing or contradictory full-access configuration
- **THEN** provisioning fails closed and does not infer, broaden, or downgrade permissions
