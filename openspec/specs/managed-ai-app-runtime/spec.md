# managed-ai-app-runtime Specification

## Purpose

Define safe, zero-configuration AI inheritance for applications created and run inside BudgetLoop workspaces.

## Requirements

### Requirement: Zero-configuration managed AI runtime
BudgetLoop SHALL, by default, make its configured AI gateway available to server-side AI applications created in an assigned workspace through process-only runtime configuration without requiring a project-specific upstream API key or secret-bearing `.env` file, and SHALL allow the operator to disable this inheritance in authenticated web settings.

#### Scenario: Generated AI application starts in a managed workspace
- **WHEN** a live run starts a server-side AI application in its assigned workspace
- **THEN** the process receives a BudgetLoop runtime base URL, scoped credential and allowed model in memory and can call the configured gateway without receiving the upstream API key

#### Scenario: Generated browser application needs AI
- **WHEN** an application includes browser-facing code
- **THEN** the generated architecture routes AI requests through its server-side component and no durable runtime or upstream credential is embedded in a public bundle

#### Scenario: Operator disables inherited AI runtime
- **WHEN** the operator turns off managed-app inheritance in web settings
- **THEN** new workspace processes receive no managed AI proxy variables or capabilities and the interface truthfully reports that project AI access requires an operator-selected alternative

### Requirement: Short-lived scoped runtime capability
BudgetLoop SHALL issue and validate signed runtime capabilities restricted to one live run, one audience, one allowed model and a bounded expiry without persisting the capability or upstream key in business tables.

#### Scenario: Valid runtime call is submitted
- **WHEN** a generated server process presents an unexpired capability for its assigned run, audience and model
- **THEN** BudgetLoop accepts the call subject to existing request and budget limits

#### Scenario: Runtime capability is invalid
- **WHEN** a capability is malformed, expired, signed with different server material, uses another audience or requests another model
- **THEN** BudgetLoop rejects the call before contacting the upstream gateway and returns no signing or upstream secret detail

### Requirement: Bounded OpenAI-compatible runtime proxy
BudgetLoop SHALL expose only an allowlisted OpenAI-compatible server-side runtime surface, validate scope before forwarding, apply configured reasoning policy and return sanitized failures without becoming a general forwarding proxy.

#### Scenario: Allowed chat completion is requested
- **WHEN** a valid scoped runtime submits a bounded Chat Completions request for its allowed model
- **THEN** BudgetLoop forwards it through the configured gateway with the enforced model and reasoning profile and returns only the compatible response and auditable usage facts

#### Scenario: Runtime request exceeds policy
- **WHEN** a request is oversized, selects another model, exceeds its run budget or targets an unsupported path
- **THEN** BudgetLoop rejects it without forwarding and records a secret-free reason code

### Requirement: Secret-free workspace lifecycle
Runtime capabilities and upstream credentials SHALL remain outside generated source, Git state, artifacts, transcripts and logs throughout provision, execution, handoff and cleanup.

#### Scenario: Workspace is inspected after execution
- **WHEN** the operator or another session inspects generated files and Git changes
- **THEN** neither the Sangfor API key nor the scoped runtime capability is present in project files or committed content

#### Scenario: Runtime event is recorded
- **WHEN** a managed AI call succeeds or fails
- **THEN** observability records bounded run, model, duration, status and usage facts without prompt, completion, capability or upstream credential content
