## MODIFIED Requirements

### Requirement: Persistent work container
The system SHALL persist a work container with a name, project goal, shared context, lifecycle state, base working directory, default workspace policy and optional immutable preset provenance and applied snapshot.

#### Scenario: Operator creates a container
- **WHEN** an authenticated operator submits a valid name, goal and absolute base working directory through the manual workflow
- **THEN** the system creates one active container and returns its stable identifier without starting an Agent session implicitly and with no preset provenance

#### Scenario: Operator creates from a preset
- **WHEN** an authenticated operator explicitly submits a valid versioned preset creation request
- **THEN** the system creates one active container with its applied preset snapshot and the requested initial sessions in the same database transaction

#### Scenario: Container input is invalid
- **WHEN** the name or goal is empty or the base working directory is not absolute
- **THEN** creation is rejected with field-specific feedback and no partial container is stored

## ADDED Requirements

### Requirement: Explicit preset team activation
A preset-created team whose runs were created for later SHALL require an explicit authenticated start operation and SHALL dispatch only eligible PENDING runs owned by that container.

#### Scenario: Operator starts a staged team
- **WHEN** the operator starts a preset-created container with PENDING session runs
- **THEN** each eligible run is submitted once and the response identifies accepted runs and actionable dispatch warnings

#### Scenario: Team start is retried
- **WHEN** the start operation is repeated after some or all runs were already accepted or became non-PENDING
- **THEN** the system skips ineligible runs and does not create new tasks, runs, budgets or sessions
