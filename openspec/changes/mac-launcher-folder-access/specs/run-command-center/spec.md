## ADDED Requirements

### Requirement: Folder access mode visibility
The run command center SHALL display the run's folder permission mode and, when present, its project folder, so the operator can tell at a glance whether the agent is isolated from or writing directly into a host folder. A full-access run SHALL be marked distinctly from an isolated run.

#### Scenario: Full-access run is open
- **WHEN** a run recorded with `full_access` and a project folder is loaded
- **THEN** the run detail shows the 完全访问模式 indicator and the folder path

#### Scenario: Isolated run is open
- **WHEN** a run without full access is loaded
- **THEN** the run detail shows the isolated mode and no host folder is implied as writable
