# guided-task-creation Specification

## Purpose

Define the guided, safe, and retryable task-creation experience while preserving the existing API contract.
## Requirements
### Requirement: Guided task setup
The task creation route SHALL group task intent, workspace and safety, and budget configuration into an understandable sequence while keeping all required fields reviewable before submission.

#### Scenario: Operator configures a standard task
- **WHEN** the operator supplies a task name, description, workspace, template, strategy, and budget
- **THEN** the interface presents the configuration in a clear hierarchy and allows the operator to review it before starting the task

### Requirement: Helpful defaults and budget presets
The creation experience SHALL provide safe existing defaults and understandable budget presets or guidance, while allowing every budget limit supported by the current API request to be edited.

#### Scenario: Operator selects a budget preset
- **WHEN** a preset is selected
- **THEN** the token, wall-time, active-runtime, call-count, cost, and parallel-call values update to the preset values and remain individually editable

#### Scenario: Operator chooses dynamic strategy
- **WHEN** the dynamic budget strategy is selected
- **THEN** the interface explains that BudgetLoop may reallocate effort under pressure without implying that configured hard limits can be exceeded

### Requirement: Inline validation and submission safety
The creation experience SHALL validate required and numeric inputs before submission, prevent duplicate in-flight submissions, and use an idempotency key with the existing create-task API.

#### Scenario: Required input is invalid
- **WHEN** the operator attempts to submit missing required text, an invalid workspace, or a non-positive required budget value
- **THEN** submission is blocked and the relevant field receives an actionable error message

#### Scenario: Task creation succeeds
- **WHEN** the API accepts a valid task request
- **THEN** the interface navigates to the returned run and does not submit a second request

#### Scenario: Task creation fails
- **WHEN** the API rejects or cannot complete the request
- **THEN** the entered configuration remains available and a trustworthy retryable error is shown

### Requirement: Explicit safety control
The creation experience SHALL present the high-risk approval setting as an explicit safety decision with plain-language consequences and SHALL transmit it unchanged in the current API payload.

#### Scenario: Approval is required
- **WHEN** the operator enables high-risk approval
- **THEN** the review state clearly indicates that qualifying actions will wait for human approval

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

### Requirement: Folder permission mode selection
The task creation flow SHALL let the operator optionally name a local project folder and choose a folder permission mode — 隔离工作区 (isolated, the default) or 完全访问模式 (full access) — before submitting. The full-access choice SHALL be presented with explicit high-risk warning copy stating that the agent will edit the selected folder directly, and submission SHALL be blocked with an inline error when full access is chosen without a folder.

#### Scenario: Default submission
- **WHEN** the operator creates a task without touching the folder options
- **THEN** the task is created with the isolated mode and no project folder, and the agent cannot modify any host folder

#### Scenario: Full access requires a folder
- **WHEN** the operator selects 完全访问模式 but leaves the folder empty
- **THEN** the form shows an inline validation error and does not submit

#### Scenario: Full access is visibly high-risk
- **WHEN** the operator selects 完全访问模式
- **THEN** the form displays warning copy explaining that agent changes will be written directly into the selected folder, including its `.git` metadata

#### Scenario: Folder selection stays in context
- **WHEN** the operator selects 完全访问模式 on any task-creation surface
- **THEN** the 选择文件夹 action appears in the same field group as 项目文件夹, the path can be entered manually in that adjacent field, and no global window-toolbar action competes with or obscures this contextual control

#### Scenario: Full access folder is entered manually
- **WHEN** the operator selects 完全访问模式 in the browser
- **THEN** the form accepts a manually typed absolute path and validates it on submission

#### Scenario: Project folder is selected before conversational planning
- **WHEN** the operator chooses a project folder from the initial conversational goal composer and then generates a suggested configuration
- **THEN** the composer shows the system-selected folder, the selection remains unchanged across AI planning, and the review opens in direct-project mode with the selected path visible and risk acknowledgement still required
