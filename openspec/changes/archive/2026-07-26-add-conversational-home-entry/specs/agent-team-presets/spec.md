## ADDED Requirements

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

