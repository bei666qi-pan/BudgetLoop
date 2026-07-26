## ADDED Requirements

### Requirement: Versioned, branded macOS release archive
The macOS launcher build SHALL embed the release version and BudgetLoop application icon in `BudgetLoop.app`, and its release archive SHALL be traceable to the corresponding GitHub tag.

#### Scenario: Operator inspects the macOS application
- **WHEN** an operator opens a macOS release archive or inspects `BudgetLoop.app`
- **THEN** macOS displays the BudgetLoop icon and the bundle reports the GitHub Release version
