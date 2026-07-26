## ADDED Requirements

### Requirement: Beginner-first inherited AI runtime
The operator workspace SHALL explain that AI applications created by BudgetLoop automatically use the configured managed gateway through a scoped server-side runtime and do not require a second project API key or secret-bearing `.env` file.

#### Scenario: Operator creates an AI application
- **WHEN** a project goal describes an AI game, writing assistant or other AI-powered application
- **THEN** the interface explains that server-side generated code will inherit BudgetLoop AI access automatically while browser code will use the generated application's server route

#### Scenario: Managed gateway is unavailable
- **WHEN** the configured gateway or aTrust route is unavailable
- **THEN** the interface shows a non-secret actionable readiness state and does not claim that the generated AI application can make remote model calls

#### Scenario: Operator inspects credential behavior
- **WHEN** the operator reviews the team or runtime configuration
- **THEN** the interface states that the upstream key stays in BudgetLoop or the OS secret store and is not copied into the generated repository

#### Scenario: Operator changes inherited runtime policy
- **WHEN** the operator opens authenticated AI settings
- **THEN** the interface exposes a default-on managed-app inheritance switch and accurately previews the effect of disabling it without revealing the saved upstream key
