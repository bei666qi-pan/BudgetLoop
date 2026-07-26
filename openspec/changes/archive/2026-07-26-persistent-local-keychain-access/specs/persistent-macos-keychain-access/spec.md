## ADDED Requirements

### Requirement: Native persistent Keychain authorization
The macOS launcher SHALL retrieve the local gateway secret through the macOS Security framework as the BudgetLoop application, using the existing exact generic-password account and service. It SHALL never log, persist, or return the secret to the browser.

#### Scenario: First native launch
- **WHEN** the local gateway Keychain item requires authorization for BudgetLoop
- **THEN** macOS presents its standard authorization UI for the signed BudgetLoop app and the launcher continues only after a successful read

#### Scenario: Previously approved launcher is reopened
- **WHEN** the same signed BudgetLoop app is reopened after persistent Keychain approval
- **THEN** it reuses the macOS authorization decision without a new application authorization prompt

### Requirement: Foreground local configuration
The packaged macOS application SHALL let each user save their own AI gateway configuration from the existing web settings page. It SHALL persist non-secret settings in the local application-support directory and the submitted key only in Keychain. It SHALL not return the key to browser JavaScript.

#### Scenario: User saves settings in the packaged app
- **WHEN** a user submits valid gateway settings from the localhost BudgetLoop settings page
- **THEN** the native app safely persists the configuration, applies it to the stateless local gateway consumers, clears the in-page key field, and later launches reuse it without requiring it again

#### Scenario: Untrusted page attempts a native save
- **WHEN** a frame that is not the main `http://localhost:3000` BudgetLoop frame sends the native bridge message
- **THEN** the app ignores the request and does not modify local settings or Keychain

### Requirement: Stable local launcher identity
The local packaging workflow SHALL prefer a persistent local code-signing identity when one is available, while retaining an explicit safe fallback for machines without that identity.

#### Scenario: Local signing identity exists
- **WHEN** `BudgetLoop Local Signing` exists in the login keychain
- **THEN** the packaged launcher is signed with that identity and remains recognisable across rebuilds

#### Scenario: Local signing identity is absent
- **WHEN** a contributor builds on a machine without the local identity
- **THEN** the build completes with ad-hoc signing and does not create, expose, or substitute a provider secret
