## ADDED Requirements

### Requirement: Agent-server conversations use a scoped managed runtime
BudgetLoop SHALL create an agent-server conversation using the managed runtime URL, short-lived run-scoped capability, and selected model provisioned for that workspace. It SHALL NOT send an upstream gateway credential to an agent-server.

#### Scenario: Managed runtime is available
- **WHEN** BudgetLoop provisions an agent-server workspace with managed AI inheritance enabled and creates its initial conversation
- **THEN** the conversation receives the workspace capability URL, scoped capability, and selected model while the upstream credential remains in the control plane

#### Scenario: Conversation resumes after recovery
- **WHEN** BudgetLoop attaches an existing agent-server workspace for a run with an existing conversation
- **THEN** it preserves the existing conversation identifier and does not create a new conversation or disclose an upstream credential

### Requirement: Agent-server credential boundary fails closed
BudgetLoop SHALL reject agent-server conversation creation when its workspace lacks a complete managed-runtime capability, and SHALL report a sanitized actionable workspace failure without falling back to the configured upstream credential.

#### Scenario: Managed inheritance is disabled
- **WHEN** the operator disables managed-app inheritance and starts an agent-server run
- **THEN** BudgetLoop fails the workspace setup before making an agent-server conversation request and directs the operator to enable the existing managed-runtime setting

#### Scenario: Capability issuance is unavailable
- **WHEN** managed inheritance is enabled but the URL, capability, model, or management marker is missing from the provisioned workspace
- **THEN** BudgetLoop makes no agent-server request with any gateway credential and records only a sanitized runtime-configuration reason
