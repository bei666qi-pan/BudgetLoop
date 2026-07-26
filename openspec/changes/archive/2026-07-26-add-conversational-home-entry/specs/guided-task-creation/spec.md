## ADDED Requirements

### Requirement: Draft-backed configuration review
The creation experience SHALL accept a server-validated conversational setup draft, show every persisted or safety-relevant value before submission, and allow bounded edits without forcing the operator through the full advanced form.

#### Scenario: Ready draft is reviewed
- **WHEN** the draft service returns a ready setup
- **THEN** the interface shows the goal, acceptance criteria, selected team and roles, aggregate starter limits, approval state, execution readiness, and folder policy in one review surface

#### Scenario: Operator edits a suggested field
- **WHEN** the operator changes an allowed title, goal, criterion, trusted preset, optional role, bounded budget, or folder choice
- **THEN** validation and aggregate summaries update before confirmation and the server revalidates the submitted values

#### Scenario: Advanced configuration is requested
- **WHEN** the operator opens progressive disclosure from the review surface
- **THEN** the existing detailed role, engine, budget, workspace, and preset controls remain available without creating a second draft

### Requirement: Permission-aware final confirmation
The final creation action SHALL summarize the effective host path, folder access mode, worktree policy, approval setting, and aggregate hard limits, and SHALL remain disabled while a required permission acknowledgement or validation fact is missing.

#### Scenario: Isolation is retained
- **WHEN** the operator keeps the default isolated mode
- **THEN** the review states that the original host folder will not be directly modified and no writable-folder acknowledgement is required

#### Scenario: Writable access is selected
- **WHEN** the operator selects full access to a project folder
- **THEN** the review names the canonical folder, explains direct writes including `.git`, explains per-session worktrees, and requires an explicit acknowledgement before confirmation

#### Scenario: Writable selection changes
- **WHEN** the operator changes the selected folder or folder access mode
- **THEN** any previous high-risk acknowledgement is cleared and must be made again for the new effective selection

