# agent-team-presets Specification

## Purpose

Define the trusted built-in Agent Team catalog, AI-first recommendation with a deterministic local fallback, editable preview, graph activation and auditable zero-configuration creation behavior.

## Requirements

### Requirement: Trusted built-in team catalog
The system SHALL load a versioned CrewAI-compatible YAML catalog of common Agent Team presets with role/goal/task definitions, MetaGPT-style SOP stages, skill labels, bounded starter budgets, workspace defaults and attributed open-source pattern references, and SHALL compile each applied topology through LangGraph.

#### Scenario: Operator browses presets
- **WHEN** the authenticated operator requests the preset catalog with or without a category filter
- **THEN** the system returns stable preset identifiers and versions, beginner-readable team summaries, complete role previews and validated LangGraph activation stages without requiring user-side framework configuration

#### Scenario: Preset source is inspected
- **WHEN** a preset references an external collaboration pattern
- **THEN** the response identifies the repository, repository URL, license, reviewed star count, review date and whether it is a direct runtime, compatible schema or attributed pattern source

### Requirement: AI-first explainable team recommendation
The system SHALL first use a bounded AI request through the configured gateway to rank only trusted built-in presets and SHALL validate all structured output against the local catalog; when AI is disabled, unconfigured, unavailable, timed out or invalid, it SHALL use the compiled local LangGraph recommendation graph and disclose the result source without failing the creation path.

#### Scenario: Healthy AI gateway recommends a known team
- **WHEN** the operator submits a valid goal while AI recommendation and its gateway model alias are healthy
- **THEN** the system returns up to three catalog-owned presets with bounded confidence, concise reasons, public matched signals and `ai` source provenance without returning hidden reasoning

#### Scenario: AI returns untrusted or malformed output
- **WHEN** the gateway response is malformed, oversized, duplicates identifiers or references a preset outside the trusted catalog
- **THEN** the system rejects the invalid AI result, runs the deterministic local graph and returns a sanitized local-fallback reason

#### Scenario: AI is unavailable
- **WHEN** AI recommendation is disabled or the gateway is missing credentials, unhealthy or exceeds its timeout
- **THEN** the local LangGraph graph returns usable recommendations and the response truthfully reports that no successful AI recommendation was used

#### Scenario: Goal matches a known domain locally
- **WHEN** the local fallback receives a goal with signals matching one or more catalog domains
- **THEN** the system returns up to three ranked presets with bounded confidence, matched public signals and a readable recommendation reason

#### Scenario: Goal has no strong local match
- **WHEN** the local fallback finds no useful catalog signal
- **THEN** the LangGraph conditional fallback routes to the generic project team, labels it as a safe fallback and still allows the operator to browse every preset

#### Scenario: Recommendation input is invalid
- **WHEN** the goal is blank, over the content bound or an optional preference is not recognized
- **THEN** the request is rejected with field-specific feedback before project text is sent to any external service

### Requirement: Open-source activation graph
The system SHALL compile each selected preset's ordered and parallel SOP stages into LangGraph and SHALL adapt the resulting activation waves and required Handoff edges to existing BudgetLoop sessions and runs.

#### Scenario: Preset topology is instantiated
- **WHEN** a valid preset is selected for creation
- **THEN** the compiled graph yields only role keys owned by that preset, persists its applied stages and dispatches eligible runs in graph activation order

#### Scenario: Preset topology is invalid
- **WHEN** a YAML stage references an unknown role, has no entry stage or cannot compile
- **THEN** catalog validation fails closed and the system does not expose or instantiate that preset

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

### Requirement: Catalog-constrained conversational team draft
The preset system SHALL support a conversational draft that selects only a trusted built-in preset and SHALL resolve the complete applied roles, tasks, starter budgets, activation plan, engine facts, and public source attribution from the catalog before the operator confirms creation.

#### Scenario: Draft selects a trusted preset
- **WHEN** the draft planner selects a known preset identifier and version
- **THEN** the returned team details exactly match catalog-owned values plus allowed bounded public text refinements

#### Scenario: Selected preset changes before confirmation
- **WHEN** the operator chooses another trusted recommendation or browses the catalog from the review surface
- **THEN** the roles, tasks, topology, source attribution, aggregate limits, and validity are recomputed from the newly selected version

### Requirement: Folder-aware preset instantiation
Preset-based team creation SHALL accept additive isolated or full-access folder settings, SHALL validate them with the same canonical policy as single-task creation, and SHALL persist the confirmed effective settings into every created run and the applied public snapshot.

#### Scenario: Isolated team is created
- **WHEN** a preset team is confirmed without writable host access
- **THEN** every created run uses isolated folder access and no host project path is required or inferred

#### Scenario: Full-access team is created
- **WHEN** a preset team is confirmed with a valid canonical project path, explicit acknowledgement, and worktree workspace policy
- **THEN** every created run receives that exact folder policy and path and every enabled session is marked for a server-generated worktree

#### Scenario: Full access is incomplete or unsafe
- **WHEN** the request omits acknowledgement or path, supplies a forbidden path, or requests full access without worktrees
- **THEN** the entire creation request is rejected before any container, session, task, run, budget, or dispatch is committed

#### Scenario: Existing client omits new fields
- **WHEN** an existing preset-creation client submits the previous request shape
- **THEN** the server defaults to isolated access and preserves the existing idempotent creation behavior

### Requirement: Draft and creation provenance
The system SHALL distinguish recommendation provenance from operator authorization and SHALL persist only public applied configuration, not prompt transcripts, hidden reasoning, provider credentials, or unconfirmed permission suggestions.

#### Scenario: AI recommendation is confirmed
- **WHEN** the operator creates a team from an AI-assisted draft
- **THEN** the applied snapshot records the preset/version, public recommendation source, allowed overrides, effective folder policy, and aggregate limits without storing chain-of-thought or secrets
