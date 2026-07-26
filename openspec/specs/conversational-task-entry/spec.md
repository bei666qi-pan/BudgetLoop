# conversational-task-entry Specification

## Purpose
Define the bounded, explainable, and confirmation-gated conversational workflow that turns a plain-language goal into a trusted Agent Team setup draft.

## Requirements

### Requirement: Plain-language home intake
The home page SHALL let an operator describe a desired outcome in plain language and SHALL turn a valid description into a reviewable setup draft without requiring agent-framework, role-topology, budget-strategy, or sandbox expertise.

#### Scenario: First-time operator describes an outcome
- **WHEN** an operator submits a meaningful plain-language goal from the home composer
- **THEN** the system returns a beginner-readable setup draft or at most two concise questions for facts that cannot receive a safe default

#### Scenario: Returning operator starts new work
- **WHEN** an operator with existing tasks opens the home page
- **THEN** the conversational intake remains the primary new-work action and recent work remains directly accessible below it

### Requirement: Bounded and validated setup draft
The draft service SHALL accept bounded input, validate all AI structured output, resolve only server-owned preset identifiers and versions, and fill roles, tasks, budgets, approval defaults, and activation topology from the trusted local catalog.

#### Scenario: AI returns a valid known setup
- **WHEN** the configured gateway returns bounded text fields and a known preset identifier in the required schema
- **THEN** the server returns a complete draft whose roles, tasks, budgets, approval default, and topology are resolved from the matching trusted catalog version

#### Scenario: AI invents configuration
- **WHEN** AI output contains an unknown preset, unknown keys, invented roles, invalid limits, duplicates, oversized content, or malformed JSON
- **THEN** the server rejects that output and returns a complete locally generated fallback draft without exposing hidden reasoning

#### Scenario: Input exceeds a bound
- **WHEN** the operator submits blank or oversized intake content
- **THEN** the request is rejected with field-specific feedback before content is sent to an external model service

### Requirement: Explainable graceful fallback
The draft service SHALL use the configured bounded AI path when healthy, SHALL fall back to the existing deterministic local recommendation when AI is unavailable or invalid, and SHALL disclose public provenance without making fallback a creation blocker.

#### Scenario: AI draft succeeds
- **WHEN** a healthy configured gateway produces a valid draft
- **THEN** the response identifies `ai` provenance, the safe model alias, the selected preset, and concise public match reasons or signals

#### Scenario: AI draft is unavailable
- **WHEN** AI is disabled, unconfigured, timed out, unreachable, or invalid
- **THEN** the response identifies `local_fallback`, includes a sanitized fallback code, and still provides a usable trusted-catalog draft

### Requirement: Safe follow-up refinement
The conversational entry SHALL allow follow-up text to refine an existing public draft while preserving server catalog bounds and SHALL keep operator-owned folder access and approval state outside AI-editable draft fields.

#### Scenario: Operator adds a constraint
- **WHEN** the operator submits follow-up text with an existing draft
- **THEN** the service updates only allowed bounded intent fields and trusted preset selection while revalidating the complete returned draft

#### Scenario: Prompt requests elevated access
- **WHEN** the description or follow-up asks the AI to grant writable folder access, disable approval, or raise budgets beyond server bounds
- **THEN** the returned draft does not apply those changes and the permission and approval controls remain explicit operator actions

### Requirement: Confirmation is the only commit boundary
Draft generation and refinement SHALL create no Task, TaskRun, WorkContainer, WorkSession, dispatch, approval, or budget record, and the system SHALL persist and dispatch work only after an explicit valid confirmation using an idempotency key.

#### Scenario: Operator previews a draft
- **WHEN** a draft reaches the ready state but the operator has not confirmed it
- **THEN** no business record or worker message is created and no project folder is mounted or modified

#### Scenario: Operator confirms a valid draft
- **WHEN** the operator confirms the visible team, limits, approval state, and folder policy
- **THEN** the system atomically creates the configured team through the preset creation contract and starts it at most once

#### Scenario: Confirmation response is lost
- **WHEN** the operator retries confirmation with the same idempotency key after an uncertain response
- **THEN** the existing team is returned without duplicate tasks, sessions, runs, budgets, or dispatches

### Requirement: Recoverable intake states
The conversational entry SHALL distinguish idle, planning, needs-input, ready, confirming, retryable error, and created states and SHALL preserve recoverable input and the latest valid draft when a safe retry is possible.

#### Scenario: Newer request replaces planning
- **WHEN** the operator edits and resubmits while an older draft request is in flight
- **THEN** the older result cannot overwrite the newer request state

#### Scenario: Draft request fails
- **WHEN** the API cannot produce either an AI or local draft
- **THEN** the composer content remains available and the interface offers a safe retry without claiming that a team was configured
