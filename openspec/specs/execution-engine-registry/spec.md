# execution-engine-registry Specification

## Purpose

Define the versioned, replaceable execution-engine boundary that keeps BudgetLoop authoritative over orchestration, safety and audit facts.

## Requirements

### Requirement: Versioned execution engine registry
The system SHALL expose OpenHands, Codex, Gemini CLI and OpenCode as typed, versioned execution engines with canonical repository, pinned source revision, reviewed Star count, license boundary, availability and supported transport.

#### Scenario: Operator inspects engines
- **WHEN** an authenticated operator loads the execution engine catalog
- **THEN** the system returns all four engines, identifies OpenHands as the compatibility default, distinguishes installed/available state from source-downloaded state and discloses any engine-specific credential requirement

#### Scenario: Upstream source is bundled
- **WHEN** the repository source bootstrap is run
- **THEN** it downloads each canonical repository at a pinned revision under `vendor/agent-engines` and excludes non-open OpenHands enterprise content

### Requirement: Replaceable execution adapter
The system SHALL route engine operations through a BudgetLoop-owned adapter contract without granting the engine authority over TaskRun state, budgets, approvals, workspaces, events or Handoffs.

#### Scenario: Team selects an engine
- **WHEN** an operator selects an available engine for a preset team or role
- **THEN** the applied snapshot and Runs record that engine and the worker invokes its adapter while retaining all existing control-plane enforcement

#### Scenario: Engine is unavailable
- **WHEN** the selected binary, service or required credential is unavailable
- **THEN** preflight fails with an actionable engine-specific error and the system does not silently fall back to another engine

#### Scenario: Existing clients omit engine
- **WHEN** a legacy task, Session or preset request omits execution-engine selection
- **THEN** the system uses the OpenHands compatibility default and preserves existing behavior
