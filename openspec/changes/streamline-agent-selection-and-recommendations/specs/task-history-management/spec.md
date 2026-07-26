## ADDED Requirements

### Requirement: Confirmed standalone task deletion
The system SHALL let an authenticated operator delete one terminal standalone task from recent history only after explicit confirmation and SHALL remove its database-owned run history transactionally without affecting any other task or infrastructure data.

#### Scenario: Operator deletes completed standalone task
- **WHEN** the operator confirms deletion of a standalone task whose runs are all terminal
- **THEN** the task and its run-owned database history are deleted in one transaction and the task disappears from recent history

#### Scenario: Operator cancels deletion
- **WHEN** the operator opens deletion confirmation and cancels it
- **THEN** no request changes task or run data and the task remains visible

#### Scenario: Deletion fails
- **WHEN** the deletion request fails or a database constraint prevents completion
- **THEN** the transaction rolls back, the task remains visible, and the interface provides a concise retryable error

### Requirement: Deletion lifecycle and ownership guards
The system MUST reject recent-history deletion for Agent Team-owned tasks and tasks with a non-terminal run, and MUST NOT delete work containers, sessions, messages, external workspace files, worktrees, PostgreSQL, Valkey, New API, or provider data.

#### Scenario: Task is still active
- **WHEN** an operator attempts to delete a task with a pending, running, paused, or waiting-approval run
- **THEN** the API returns a conflict response and preserves the complete task history

#### Scenario: Task belongs to an Agent Team
- **WHEN** an operator attempts to delete a task referenced by a work session
- **THEN** the API returns a conflict response and preserves the task, session, and container

#### Scenario: Task does not exist
- **WHEN** an operator requests deletion for an unknown task identifier
- **THEN** the API returns not found and changes no data
