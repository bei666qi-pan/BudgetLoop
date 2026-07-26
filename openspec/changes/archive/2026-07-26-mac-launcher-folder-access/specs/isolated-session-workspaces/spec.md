## ADDED Requirements

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
