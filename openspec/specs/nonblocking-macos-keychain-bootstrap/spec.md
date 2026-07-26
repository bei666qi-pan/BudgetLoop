# nonblocking-macos-keychain-bootstrap Specification

## Purpose
TBD - created by archiving change nonblocking-local-keychain-bootstrap. Update Purpose after archive.
## Requirements
### Requirement: Automatic Keychain bootstrap never blocks startup
The macOS launcher SHALL perform automatic local Keychain reads without presenting or waiting for authorization UI. If the saved secret is unavailable without interaction, it SHALL continue startup in a redacted unconfigured state and preserve the existing local settings page as the user-facing recovery path.

#### Scenario: Saved key is available without interaction
- **WHEN** the signed BudgetLoop app is opened after a user has saved an accessible local gateway key
- **THEN** it reads the key without prompting, injects it only into the local compose child process, and opens normally

#### Scenario: Legacy key requires authorization
- **WHEN** a local Keychain item would require interactive authorization during launcher bootstrap
- **THEN** the launcher does not block or show an authorization prompt, does not disclose the key, and opens its normal foreground configuration path

### Requirement: Keychain remains local storage rather than configuration UX
The system SHALL keep each user's gateway settings and credential entry in the authenticated foreground BudgetLoop settings experience; Keychain SHALL only hold the current Mac's secret implementation detail.

#### Scenario: User replaces an unavailable local key
- **WHEN** a user enters a valid API key in BudgetLoop's foreground settings page
- **THEN** the app saves it locally using the existing native bridge, clears the browser input, and later automatic launches can reuse it without a configuration prompt
