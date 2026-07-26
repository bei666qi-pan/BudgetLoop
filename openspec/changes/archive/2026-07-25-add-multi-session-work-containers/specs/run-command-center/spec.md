## MODIFIED Requirements

### Requirement: Run state hierarchy
The run route SHALL prioritize run status, current phase/activity, task identity, owning work container/session when present, elapsed or completion context, and the most useful next action ahead of secondary diagnostics.

#### Scenario: Run is active
- **WHEN** a non-terminal run is loaded
- **THEN** the operator can identify what the agent is doing, whether the connection is current, and where to inspect progress without interpreting raw events first

#### Scenario: Container-owned run is active
- **WHEN** a run belongs to a work session
- **THEN** the command center exposes a safe return path to the owning container and identifies the session role without revealing other sessions' private context

#### Scenario: Run is terminal
- **WHEN** the run reaches a terminal state
- **THEN** the interface stops presenting it as live and offers the final report when available

## ADDED Requirements

### Requirement: Collaboration delivery observability
The run command center SHALL expose collaboration delivery events as attributed operational facts without presenting them as model reasoning.

#### Scenario: Session inbox is delivered
- **WHEN** queued cross-session messages are included in an Agent iteration
- **THEN** the event timeline records message identifiers and sender/recipient attribution while private content remains available only in the owning session transcript
