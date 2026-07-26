## ADDED Requirements

### Requirement: Double-clickable application bundle
The project SHALL provide a macOS application bundle (`BudgetLoop.app`) built from the `desktop/` launcher project with the system Swift toolchain, requiring no Xcode project and no third-party packaging dependency. Launching the app SHALL bring the operator to the BudgetLoop web UI in a native application window when the local stack is or becomes healthy.

#### Scenario: Cold launch with Docker running
- **WHEN** the operator opens the app and Docker Desktop is already running
- **THEN** the app starts the required compose services, waits for health, and opens a native window showing the web UI

#### Scenario: Docker Desktop not running
- **WHEN** the operator opens the app and Docker Desktop is installed but not running
- **THEN** the app starts Docker Desktop, waits for the daemon, and continues the normal bring-up

### Requirement: Environment materialization and gateway bootstrap
On first launch the app SHALL materialize a working `.env` from the committed example with generated secrets, never overwriting an existing `.env`. When a locally saved compatible AI-gateway configuration exists (including its Keychain credential), the app SHALL inject it into the stack environment so runs can execute without manual gateway console setup.

#### Scenario: First launch without .env
- **WHEN** the app launches and no `.env` exists in the repository
- **THEN** it creates one with generated secrets and proceeds

#### Scenario: Existing local gateway settings
- **WHEN** the user's local gateway settings and Keychain credential are present
- **THEN** the compose stack starts with those gateway settings and the gateway status endpoint reports configured

#### Scenario: No gateway configuration available
- **WHEN** no local gateway configuration or credential can be found
- **THEN** the app shows a guided setup pane (including a link to the gateway console) instead of a bare failure

### Requirement: Health gating with readable failures
The app SHALL gate window presentation on the control-plane, gateway, and web health checks, and SHALL present failures as readable states that name the failed step and a concrete remedy.

#### Scenario: Port conflict
- **WHEN** a required port is already bound by an unhealthy or foreign process
- **THEN** the app reports which port conflicts and how to free it, without crashing

#### Scenario: Healthy stack already running
- **WHEN** the control-plane and web endpoints already answer health checks before the app starts anything
- **THEN** the app attaches to the running stack and opens the window without restarting services

### Requirement: Graceful teardown
When the operator closes the app window, the app SHALL stop the compose services it started itself, and SHALL leave any pre-existing (adopted) services running.

#### Scenario: App started the stack
- **WHEN** the window closes after the app itself brought the stack up
- **THEN** the app stops those services gracefully

#### Scenario: App adopted a running stack
- **WHEN** the window closes after the app attached to an already-running stack
- **THEN** those services keep running

### Requirement: Native folder picker bridge
The app window SHALL offer a native folder picker that fills the task form's project-folder field, as an additive convenience that the web UI does not depend on.

#### Scenario: Operator picks a folder natively
- **WHEN** the operator uses the app's folder picker while creating a task
- **THEN** the chosen absolute path is filled into the task form's folder field
