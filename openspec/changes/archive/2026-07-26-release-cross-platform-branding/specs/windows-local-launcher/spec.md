## ADDED Requirements

### Requirement: Versioned, branded Windows MSI
The Windows launcher build SHALL embed the release version and BudgetLoop icon in its Tauri MSI and SHALL attach that MSI only to the corresponding GitHub release tag after its Windows build gate passes.

#### Scenario: Operator inspects the Windows installer
- **WHEN** an operator downloads or installs the Windows MSI from a GitHub Release
- **THEN** Windows identifies it as BudgetLoop with the BudgetLoop icon and the installer version matches the release tag
