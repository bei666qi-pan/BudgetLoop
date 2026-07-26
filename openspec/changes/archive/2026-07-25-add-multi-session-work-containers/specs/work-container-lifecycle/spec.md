## ADDED Requirements

### Requirement: Persistent work container
The system SHALL persist a work container with a name, project goal, shared context, lifecycle state, base working directory and default workspace policy.

#### Scenario: Operator creates a container
- **WHEN** an authenticated operator submits a valid name, goal and absolute base working directory
- **THEN** the system creates one active container and returns its stable identifier without starting an Agent session implicitly

#### Scenario: Container input is invalid
- **WHEN** the name or goal is empty or the base working directory is not absolute
- **THEN** creation is rejected with field-specific feedback and no partial container is stored

### Requirement: Container session membership
The system SHALL list only sessions owned by the requested work container and SHALL preserve their independent role, goal, context, status and current run linkage.

#### Scenario: Operator opens a container
- **WHEN** the container exists
- **THEN** the response includes container facts and ordered session summaries with derived live and attention counts

#### Scenario: Nested session does not belong to container
- **WHEN** a session identifier is requested under a different container identifier
- **THEN** the system returns not found without exposing the foreign session

### Requirement: Backward-compatible project operation
Existing tasks and runs that have no work-session ownership SHALL continue to operate through the legacy task workflow.

#### Scenario: Legacy task is loaded after migration
- **WHEN** an existing task or run has no work-session relationship
- **THEN** its API representation and execution behavior remain valid and container fields are absent or null

### Requirement: Trustworthy container lifecycle
The interface SHALL distinguish active, paused, completed and archived container states and SHALL derive live execution summaries from session runs rather than inventing progress.

#### Scenario: Container has mixed session states
- **WHEN** some sessions are running, waiting or terminal
- **THEN** the container summary reports those counts and does not collapse them into a false single run state
