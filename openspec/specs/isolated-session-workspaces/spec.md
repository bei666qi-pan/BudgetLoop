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
Every enabled session in a full-access preset team SHALL operate in a unique server-generated Git worktree derived from its session identifier and SHALL never execute concurrently in the selected repository root. A full-access team SHALL select a server execution engine that can mount the confirmed host project.

#### Scenario: Full-access sessions provision successfully
- **WHEN** confirmed team runs provision the writable host project through the supported server execution engine
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

### Requirement: Uploaded snapshot workspace initialization
An isolated run SHALL be initializable from an opaque, validated browser upload snapshot, SHALL copy that snapshot into its own workspace before the Git baseline is created, and SHALL NOT translate the upload into a host-folder mount or broader access mode.

#### Scenario: Agent Team starts from an uploaded project
- **WHEN** an isolated Agent Team is created with a valid project upload identifier
- **THEN** every session receives an independent workspace copy of the same uploaded files before work begins

#### Scenario: Upload snapshot is missing or invalid at provisioning
- **WHEN** a recorded upload identifier cannot be resolved to a valid snapshot below the configured upload root
- **THEN** workspace provisioning fails visibly and does not continue with an empty workspace or full-access fallback

#### Scenario: Upload identifier is combined with direct access
- **WHEN** task creation combines a project upload identifier with full-access mode or a host project directory
- **THEN** the API rejects the request and creates no team or run

### Requirement: Host folder full-access workspace mode
Workspace provisioning SHALL support a per-run folder access mode persisted with the run, with `isolated` as the default and `full_access` as an explicit opt-in. In `isolated` mode the agent SHALL write only to the run's isolated workspace volume, leaving any host folder untouched. In `full_access` mode the provisioner SHALL bind-mount the validated host project directory read-write at the container workspace mount point, so agent edits land directly in that folder, and SHALL skip fixture copying into the workspace.

#### Scenario: Isolated run with a project folder recorded
- **WHEN** a run has a project folder recorded but its access mode is `isolated`
- **THEN** the workspace is provisioned with the isolated volume only and the host folder's contents are not modified

#### Scenario: Full-access run edits the host folder
- **WHEN** a run has access mode `full_access` and a valid project directory
- **THEN** the workspace container mounts that directory read-write at the workspace mount point and agent file edits are visible in the host folder during and after the run

#### Scenario: Git baseline in a full-access workspace
- **WHEN** a full-access workspace is prepared and the mounted folder already contains a `.git` directory
- **THEN** the existing repository is reused for the baseline and is not re-initialized

### Requirement: Fail-closed folder mount setup
The provisioner SHALL reject a full-access run whose project directory is missing, invalid, or disallowed, and SHALL NOT silently fall back to isolated provisioning for a run recorded as `full_access`.

#### Scenario: Project directory cannot be mounted
- **WHEN** a full-access run's project directory fails validation or the container runtime rejects the mount
- **THEN** provisioning fails with a readable error naming the folder and the run does not start against a different location

### Requirement: Project directory validation
The task API SHALL accept an optional project directory only together with an explicit access mode, SHALL require the project directory when the mode is `full_access`, and SHALL reject non-absolute paths and sensitive roots (`/`, the user's home directory itself, and system locations such as `/System`, `/usr`, `/bin`, `/etc`, `/var`, `/private`, `/Applications`, `/Library`).

#### Scenario: Full access without a folder
- **WHEN** a task creation request sets `folder_access` to `full_access` without a project directory
- **THEN** the API rejects the request with a validation error and creates no run

#### Scenario: Sensitive root is rejected
- **WHEN** a task creation request names a system location or the filesystem root as the project directory
- **THEN** the API rejects the request with a validation error identifying the disallowed location

### Requirement: Session workspace status reflects provisioning failure
The worker SHALL persist `PROVISIONING` before it waits for a session workspace and SHALL persist `FAILED` with an actionable sanitized workspace error if provisioning fails. It SHALL NOT leave a failed workspace as `PENDING`, `PROVISIONING`, or `READY`.

#### Scenario: Agent-server cannot become healthy
- **WHEN** a session workspace health check times out or reports an unrecoverable startup error
- **THEN** its work session reports `workspace_status` `FAILED` with the corresponding readable error and its run becomes terminally failed
