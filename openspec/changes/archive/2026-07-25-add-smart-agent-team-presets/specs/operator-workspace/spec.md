## ADDED Requirements

### Requirement: Beginner-first Agent Team creation
The operator workspace SHALL make smart recommendation and ready-to-use presets the primary Agent Team creation path while preserving an advanced manual path.

#### Scenario: First-time operator describes a goal
- **WHEN** the operator enters a meaningful project goal
- **THEN** the interface can load a ranked recommendation, explain why it matches and present a complete editable team preview without asking for framework or provider configuration

#### Scenario: Operator browses instead of describing
- **WHEN** the operator selects preset browsing
- **THEN** the interface provides category filters and readable open-list rows for common teams and updates one shared preview when a preset is selected

#### Scenario: Operator chooses immediate or later start
- **WHEN** the team preview is valid
- **THEN** one primary action creates and starts the team and one secondary action creates it for later, with distinct in-flight, success and error feedback

#### Scenario: Creation is viewed on mobile
- **WHEN** the route is rendered at a narrow viewport
- **THEN** recommendation, role inspection and preset browsing remain usable without horizontal overflow and the aggregate budget plus creation action remain reachable in a mobile action region
