## ADDED Requirements

### Requirement: Persistent BudgetLoop brand mark
The web application SHALL render the BudgetLoop interlocking-loop mark in the persistent application shell and SHALL provide an equivalent branded web metadata icon. The mark SHALL have a meaningful accessible name where it is interactive and SHALL not add non-essential motion to the persistent navigation.

#### Scenario: Operator opens a primary web route
- **WHEN** the operator visits any route rendered inside the application shell
- **THEN** the header displays the recognizable BudgetLoop interlocking-loop mark next to the product name without reducing navigation accessibility or responsive usability

#### Scenario: Browser displays site metadata
- **WHEN** a browser requests the BudgetLoop application icon
- **THEN** it receives a vector or raster icon based on the same interlocking-loop brand geometry used by the product shell
