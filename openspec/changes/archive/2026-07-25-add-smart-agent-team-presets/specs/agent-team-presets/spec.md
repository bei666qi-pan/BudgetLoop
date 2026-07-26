## ADDED Requirements

### Requirement: Trusted built-in team catalog
The system SHALL load a versioned CrewAI-compatible YAML catalog of common Agent Team presets with role/goal/task definitions, MetaGPT-style SOP stages, skill labels, bounded starter budgets, workspace defaults and attributed open-source pattern references, and SHALL compile each applied topology through LangGraph.

#### Scenario: Operator browses presets
- **WHEN** the authenticated operator requests the preset catalog with or without a category filter
- **THEN** the system returns stable preset identifiers and versions, beginner-readable team summaries, complete role previews and validated LangGraph activation stages without requiring user-side framework configuration

#### Scenario: Preset source is inspected
- **WHEN** a preset references an external collaboration pattern
- **THEN** the response identifies the repository, repository URL, license, reviewed star count, review date and whether it is a direct runtime, compatible schema or attributed pattern source

### Requirement: Local explainable team recommendation
The system SHALL use a compiled local LangGraph recommendation graph to rank presets from a bounded project goal and optional industry, delivery pace and risk preferences and SHALL return concise match reasons without external model or repository calls.

#### Scenario: Goal matches a known domain
- **WHEN** the operator describes a goal with signals matching one or more catalog domains
- **THEN** the system returns up to three ranked presets with bounded confidence, matched public signals and a readable recommendation reason

#### Scenario: Goal has no strong match
- **WHEN** the submitted goal contains no useful catalog signal
- **THEN** the LangGraph conditional fallback routes to the generic project team, labels it as a safe fallback and still allows the operator to browse every preset

### Requirement: Open-source activation graph
The system SHALL compile each selected preset's ordered and parallel SOP stages into LangGraph and SHALL adapt the resulting activation waves and required Handoff edges to existing BudgetLoop sessions and runs.

#### Scenario: Preset topology is instantiated
- **WHEN** a valid preset is selected for creation
- **THEN** the compiled graph yields only role keys owned by that preset, persists its applied stages and dispatches eligible runs in graph activation order

#### Scenario: Preset topology is invalid
- **WHEN** a YAML stage references an unknown role, has no entry stage or cannot compile
- **THEN** catalog validation fails closed and the system does not expose or instantiate that preset

#### Scenario: Recommendation input is invalid
- **WHEN** the goal is blank, over the content bound or an optional preference is not recognized
- **THEN** the request is rejected with field-specific feedback and no project text is sent to an external service

### Requirement: Safe editable preset preview
The creation flow SHALL show the selected roles, goals, skills, coordination pattern, source attribution, workspace default and aggregate starter budgets before creating a team and SHALL allow bounded role overrides.

#### Scenario: Beginner accepts defaults
- **WHEN** the operator selects a recommendation or catalog preset without editing advanced settings
- **THEN** the preview contains a complete valid team that can be created without additional configuration

#### Scenario: Operator adjusts roles
- **WHEN** the operator enables or disables optional roles or changes an allowed goal or budget value
- **THEN** the preview and aggregate limits update and the server accepts only 2–8 enabled roles with budgets inside configured safety bounds

### Requirement: Idempotent zero-configuration team creation
The system SHALL instantiate a selected preset as one work container and its initial sessions, Tasks, TaskRuns, budgets and phases in a single database transaction using an idempotency key.

#### Scenario: Operator creates and starts
- **WHEN** a valid preset creation request explicitly selects immediate start
- **THEN** the system commits exactly one container and its enabled roles, dispatches their PENDING runs after commit and returns the created team plus any dispatch warnings

#### Scenario: Operator creates for later
- **WHEN** a valid preset creation request selects start later
- **THEN** the system commits the complete team with PENDING runs and does not enqueue them until an explicit team start request

#### Scenario: Preset creation is retried
- **WHEN** the same idempotency key is submitted again
- **THEN** the existing container and sessions are returned without creating or dispatching duplicates

#### Scenario: Any role fails database validation
- **WHEN** one role, budget, task or phase cannot be persisted during preset creation
- **THEN** the entire database operation rolls back and no partial team remains

### Requirement: Auditable applied preset provenance
The system SHALL persist the selected preset identifier, version and exact public applied snapshot on the work container without storing credentials, transcripts or hidden recommendation internals in that snapshot.

#### Scenario: Catalog changes after creation
- **WHEN** a newer version of the same preset becomes available
- **THEN** the existing container continues to expose the version and applied role/budget snapshot used at creation

#### Scenario: Manual container is loaded
- **WHEN** a container was created through the existing manual workflow
- **THEN** preset provenance fields remain absent or null and its behavior is unchanged
