# managed-runtime-budget-accounting Delta Specification

## Purpose

Extend managed runtime budget accounting to support team-level observatory requirements: team-level budget aggregation (SUM across sessions excluding completed/failed reserved), reservation consistency across team pause operations, team budget adjustment enforcement with a used+reserved floor, and guarantee of no double-counting in team-wide usage aggregates. PostgreSQL remains the sole source of truth for all budget data.

## ADDED Requirements

### Requirement: Team-level budget aggregation
BudgetLoop SHALL provide a team-level budget aggregation query that returns the sum of used and reserved tokens, calls, and cost across all sessions in a work container. The aggregation SHALL exclude reserved values from sessions whose status is completed, failed, or cancelled — only RUNNING and QUEUED session reserved values count toward "currently reserved." The team budget maximum SHALL be the sum of per-session max values, excluding sessions with unlimited max budgets (which display as "∞").

#### Scenario: Team usage aggregates across active and terminal sessions
- **WHEN** a work container has sessions in RUNNING, QUEUED, COMPLETED, and FAILED states
- **THEN** the team aggregation returns used = SUM(all sessions' task_budget.used_calls/used_tokens), reserved = SUM(only RUNNING and QUEUED sessions' task_budget.reserved_calls/reserved_tokens), and max = SUM(non-unlimited sessions' task_budget.max_calls/max_tokens)

#### Scenario: Team usage query when all sessions are terminal
- **WHEN** all sessions in the work container are in COMPLETED, FAILED, or CANCELLED status
- **THEN** the team aggregation returns reserved = 0 and used reflects all historical settled usage

### Requirement: Team budget adjustment floor
BudgetLoop SHALL reject any budget adjustment that would set a session's max budget below the sum of its current used and reserved values. The rejection SHALL return HTTP 422 with the current used, reserved, and proposed max values in the response body. The same floor constraint SHALL apply to team-level budget redistribution across sessions.

#### Scenario: Budget adjustment rejected below used+reserved floor
- **WHEN** an operator attempts to PATCH a session's max budget to a value less than its current used + reserved
- **THEN** the request is rejected with HTTP 422 and the response body includes current used and reserved values

#### Scenario: Budget adjustment accepted at or above floor
- **WHEN** an operator PATCHes a session's max budget to a value greater than or equal to its current used + reserved
- **THEN** the budget is updated successfully and a team audit event is recorded with old and new max values

#### Scenario: Budget increase does not silently resume
- **WHEN** a session's budget is increased after exhaustion but no explicit resume is issued
- **THEN** the response includes `needs_resume: true` and the session remains paused until an explicit resume command is received

### Requirement: No double-counting in team aggregate
BudgetLoop SHALL ensure that team-level budget aggregation counts each settled LLM call exactly once. The aggregation SHALL NOT duplicate or re-settle usage that was already recorded by the managed runtime proxy at the individual session level. The team aggregate used total SHALL equal the arithmetic sum of per-session task_budget.used_* values from PostgreSQL.

#### Scenario: Team aggregate matches per-session settled usage
- **WHEN** multiple sessions have independently settled LLM calls through the managed runtime proxy
- **THEN** the team aggregate used calls and tokens equal the arithmetic sum of each session's task_budget.used_calls and task_budget.used_tokens respectively

#### Scenario: Session usage appears once in team aggregate after completion
- **WHEN** a session completes and its settled usage is finalized
- **THEN** that session's usage is counted exactly once in all subsequent team aggregate queries and is never duplicated

## MODIFIED Requirements

### Requirement: Outer iteration reservation remains bounded and releasable
BudgetLoop SHALL retain the worker's outer iteration reservation while managed agent execution is in flight and SHALL release that reservation after execution, failure, or team-level pause without altering the proxy-settled used totals.

#### Scenario: Managed iteration reaches observation
- **WHEN** the managed agent execution completes and observation data is persisted
- **THEN** the outer estimated reservation becomes zero and no extra used call or token amount is added

#### Scenario: Non-managed execution completes
- **WHEN** an execution transport does not use BudgetLoop's managed runtime proxy
- **THEN** the worker retains its existing reserve-and-settle accounting behavior

#### Scenario: Team pause triggers reservation release for all running sessions
- **WHEN** a work container receives a pause command and one or more sessions are in RUNNING status with active outer iteration reservations
- **THEN** the reserved fields for all RUNNING sessions within the container are set to zero and no session can start a new LLM call relying on a stale reservation
