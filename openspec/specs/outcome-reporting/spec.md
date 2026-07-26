# outcome-reporting Specification

## Purpose

Define answer-first outcome reporting, evidence disclosure, authenticated exports, and unavailable-report recovery.

## Requirements

### Requirement: Answer-first outcome summary
The report route SHALL lead with terminal status, whether acceptance criteria were met, task identity, and the most relevant follow-up action before presenting detailed evidence.

#### Scenario: Acceptance criteria are met
- **WHEN** a completed report indicates successful acceptance
- **THEN** the report clearly states success and summarizes the evidence without requiring the operator to inspect raw totals first

#### Scenario: Work is partial or budget-exhausted
- **WHEN** the report status indicates partial completion or exhausted budget
- **THEN** the report distinguishes achieved work from unresolved work and preserves the backend's explanation

### Requirement: Outcome evidence and resource totals
The report SHALL present acceptance evidence, iterations, active runtime, token use, cost, call count, progress score, changed files, diff summary, strategy changes, issues, and suggestions when those fields are available.

#### Scenario: Optional report data is absent
- **WHEN** an optional evidence section has no data
- **THEN** the report omits or labels that section appropriately without fabricating metrics or errors

### Requirement: Authenticated report export
The report SHALL download JSON and Markdown exports through the authenticated frontend API helper and SHALL communicate export failures.

#### Scenario: Operator exports a report
- **WHEN** the operator selects JSON or Markdown export
- **THEN** the browser downloads the corresponding report using the configured API authorization

#### Scenario: Export fails
- **WHEN** the export endpoint rejects or cannot complete the request
- **THEN** the report shows an actionable error and remains usable

### Requirement: Report-unavailable state
The report route SHALL distinguish a report that is not yet available from a failed page request and SHALL provide a useful return or retry action.

#### Scenario: Report has not been generated
- **WHEN** the run exists but the report endpoint returns no report-ready data
- **THEN** the operator is told that the report may still be pending and can return to the run or retry
