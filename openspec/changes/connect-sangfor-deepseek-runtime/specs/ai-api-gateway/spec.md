## ADDED Requirements

### Requirement: Web-managed local gateway personalization
BudgetLoop SHALL provide an authenticated web settings flow for local gateway URL, model aliases, deployment/network labels, reasoning policy and secret replacement without hardcoding one operator's provider values as product defaults.

#### Scenario: Operator saves this installation's gateway
- **WHEN** the operator enters a valid compatible URL, DeepSeek V4 Pro model, maximum reasoning policy, Sangfor/aTrust labels and optional replacement token
- **THEN** BudgetLoop atomically stores only non-secret personalization locally, stores the token in macOS Keychain and returns a redacted configuration with `secret_configured` instead of the token

#### Scenario: Personalized secure route is unavailable
- **WHEN** the configured enterprise network client is absent, disconnected or the internal TLS route times out
- **THEN** readiness uses the configured provider/network labels with a sanitized unreachable state and BudgetLoop does not bypass network controls or expose raw internal errors

#### Scenario: Settings page is reopened
- **WHEN** the operator loads the settings after saving a token
- **THEN** the API and page show that a secret is configured but never return, prefill or render the secret value

### Requirement: Maximum DeepSeek reasoning policy
BudgetLoop SHALL request the strongest configured DeepSeek V4 Pro reasoning effort, enable thinking with a bounded maximum thinking-token budget and SHALL NOT silently downgrade those settings when the upstream rejects them.

#### Scenario: DeepSeek request is sent
- **WHEN** BudgetLoop sends an AI recommendation, execution or managed-runtime call through the Sangfor profile
- **THEN** the request includes the configured maximum reasoning effort and enabled thinking policy while hidden reasoning content remains excluded from public transcripts

#### Scenario: Maximum reasoning fields are incompatible
- **WHEN** the Sangfor endpoint rejects the configured maximum reasoning profile
- **THEN** BudgetLoop returns a sanitized rejected-request or compatibility state and identifies the profile requiring operator review without retrying at a lower effort

## MODIFIED Requirements

### Requirement: Typed replaceable gateway configuration
BudgetLoop SHALL select exactly one typed gateway mode from New API, legacy LiteLLM or an operator-supplied compatible endpoint and SHALL resolve gateway URL, server-side token, console URL, default and purpose-model aliases, reasoning effort and thinking policy from server configuration or an approved local secret loader.

#### Scenario: New API is configured
- **WHEN** the required New API URL, gateway token and recommendation alias are present
- **THEN** the control plane reports the gateway as configured and uses its OpenAI-compatible surface for bounded internal recommendation calls

#### Scenario: Compatible personalized profile is configured
- **WHEN** saved local settings supply a compatible URL, Keychain-owned token, model and reasoning policy
- **THEN** the control plane uses the compatible surface without persisting or publicly serializing the token

#### Scenario: Legacy deployment is upgraded
- **WHEN** only the existing LiteLLM URL and master key are configured
- **THEN** the system continues in explicit LiteLLM compatibility mode without copying or exposing the legacy key

#### Scenario: Configuration is incomplete
- **WHEN** a gateway mode lacks its required URL, key or recommendation model
- **THEN** health reporting identifies an actionable sanitized configuration reason and no remote recommendation request is attempted

### Requirement: Server-side secret boundary
Gateway and upstream credentials SHALL remain in server-side configuration, the New API credential store or an approved OS secret store and SHALL NOT be persisted in BudgetLoop business tables, generated project files, returned by BudgetLoop APIs, embedded in browser bundles or written to logs; managed applications SHALL receive only short-lived scoped BudgetLoop capabilities.

#### Scenario: Public configuration is serialized
- **WHEN** the frontend requests gateway status or recommendation provenance
- **THEN** the response contains no API key, authorization header, provider credential, scoped runtime capability or reversible secret fragment

#### Scenario: Generated application is provisioned
- **WHEN** a managed AI application starts in a BudgetLoop workspace
- **THEN** the real upstream credential remains server-side and only a bounded scoped capability is provided to the child process in memory

#### Scenario: Recommendation or runtime request fails
- **WHEN** an upstream exception contains a URL, header or token-like value
- **THEN** the client maps it to a stable public failure code and does not include the raw exception in the API response
