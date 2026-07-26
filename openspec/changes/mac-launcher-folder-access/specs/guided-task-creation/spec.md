## ADDED Requirements

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
- **THEN** the 选择文件夹 action appears in the same field group as 项目文件夹, the system-selected path is shown read-only in that adjacent field, manual path entry is unavailable, and no global window-toolbar action competes with or obscures this contextual control

#### Scenario: Native folder selection is unavailable in a browser
- **WHEN** the operator activates 选择文件夹 outside the BudgetLoop macOS App where the native bridge is unavailable
- **THEN** the form explains that system folder selection requires the macOS App and does not accept a manually typed absolute path as a substitute

#### Scenario: Project folder is selected before conversational planning
- **WHEN** the operator chooses a project folder from the initial conversational goal composer and then generates a suggested configuration
- **THEN** the composer shows the system-selected folder, the selection remains unchanged across AI planning, and the review opens in direct-project mode with the selected path visible and risk acknowledgement still required
