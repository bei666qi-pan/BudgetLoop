# unlimited-agent-team-budget Specification

## Purpose

Define the explicit Max budget option for preset Agent Teams while preserving accounting, controls, and audit evidence.

## Requirements

### Requirement: Explicit Max team budget
The preset-team setup SHALL offer a distinct `Max` budget choice, SHALL require explicit operator selection, and SHALL persist `budget_mode=max` only for the created preset team and its runs. The interface SHALL state that Max removes automatic resource limits and that the operator can still pause or cancel work.

#### Scenario: Operator selects Max
- **WHEN** an operator creates a valid preset team with Max budget selected
- **THEN** every enabled run is created in Max mode and the team detail exposes that it has no automatic resource cap

#### Scenario: Operator keeps the default budget
- **WHEN** an operator does not select Max
- **THEN** all existing bounded role budget validation and enforcement continue unchanged

### Requirement: Unlimited run accounting and completion safeguards
For a Max-mode run, the system SHALL continue to record actual tokens, calls, cost, runtime, public events, approvals, and final reports while omitting automatic token, call, cost, wall-clock, active-runtime, phase, and loop-iteration termination. The run SHALL end only through existing successful acceptance/completion or explicit operator lifecycle control.

#### Scenario: Max-mode usage is recorded
- **WHEN** a Max-mode run makes model calls
- **THEN** its actual usage increases in the normal accounting records and API snapshot identifies the budget as unlimited rather than reporting a synthetic remaining allowance

#### Scenario: Max-mode run continues after a formerly bounded threshold
- **WHEN** a Max-mode run reaches a value that would exhaust a bounded token, call, cost, time, or iteration limit
- **THEN** it is not marked budget exhausted or partial completed solely because of that value

#### Scenario: Operator stops a Max-mode run
- **WHEN** an operator pauses or cancels a Max-mode run through the existing lifecycle controls
- **THEN** the run transitions under the existing state rules and no further autonomous stage is released from that stopped run
