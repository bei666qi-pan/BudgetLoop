## MODIFIED Requirements

### Requirement: Beginner-first Agent Team creation
The operator workspace SHALL make AI-assisted smart recommendation and ready-to-use presets the primary Agent Team creation path while preserving deterministic local recommendation and an advanced manual path, and SHALL explain the active recommendation source without exposing gateway secrets.

#### Scenario: First-time operator describes a goal
- **WHEN** the operator enters a meaningful project goal
- **THEN** the interface can load a ranked recommendation, explain why it matches and present a complete editable team preview without asking for framework or provider configuration

#### Scenario: AI recommendation is ready
- **WHEN** the gateway status reports a healthy configured recommendation model
- **THEN** the interface states that AI-assisted recommendation is available, identifies the audited gateway and explains that submitted recommendation fields may be sent to it

#### Scenario: Local recommendation is active
- **WHEN** AI is disabled, unconfigured or a recommendation request falls back
- **THEN** the interface remains usable, labels the result as local deterministic matching and presents actionable gateway recovery guidance without treating fallback as a creation error

#### Scenario: Operator opens gateway administration
- **WHEN** a safe New API console URL is configured and the operator chooses gateway settings
- **THEN** the interface opens the upstream New API console separately rather than collecting provider credentials inside BudgetLoop

#### Scenario: Operator browses instead of describing
- **WHEN** the operator selects preset browsing
- **THEN** the interface provides category filters and readable open-list rows for common teams and updates one shared preview when a preset is selected

#### Scenario: Operator chooses immediate or later start
- **WHEN** the team preview is valid
- **THEN** one primary action creates and starts the team and one secondary action creates it for later, with distinct in-flight, success and error feedback

#### Scenario: Creation is viewed on mobile
- **WHEN** the route is rendered at a narrow viewport
- **THEN** gateway status, recommendation, role inspection and preset browsing remain usable without horizontal overflow and the aggregate budget plus creation action remain reachable in a mobile action region
