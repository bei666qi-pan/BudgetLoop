## ADDED Requirements

### Requirement: Agent Team startup feedback is truthful and actionable
The Agent Team workspace SHALL present the selected session's persisted startup lifecycle with a recognizable activity mark, concise accessible status text, and elapsed waiting time when a start timestamp is available. It SHALL derive its stage only from run, workspace, and session state returned by the control plane and SHALL NOT show simulated completion percentages.

#### Scenario: Workspace is provisioning
- **WHEN** the selected session reports a non-terminal planning state and `workspace_status` is `PROVISIONING`
- **THEN** the workspace displays that the workspace is being prepared, shows the shared BudgetLoop activity mark, and announces the status without implying that agent execution has begun

#### Scenario: Workspace is ready while agent starts
- **WHEN** the selected session reports a non-terminal planning state and `workspace_status` is `READY`
- **THEN** the workspace displays that the workspace is ready and the agent is starting, including elapsed waiting time when its persisted run start time is available

#### Scenario: Startup fails
- **WHEN** the selected session reports `workspace_status` `FAILED` or a failed run before first execution
- **THEN** the workspace displays an alert with the persisted sanitized workspace error, identifies the failed stage, and does not continue showing an active waiting indicator

### Requirement: Startup feedback remains accessible and responsive
The startup and failure panels SHALL remain readable at narrow and desktop widths, expose a text alternative for their icon and state, and honor the shared reduced-motion behavior.

#### Scenario: Operator uses reduced motion
- **WHEN** the user agent requests reduced motion while a session is provisioning
- **THEN** the activity mark remains recognizable without non-essential animation and the text status remains available
