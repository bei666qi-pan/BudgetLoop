## ADDED Requirements

### Requirement: Maintained open-source gateway foundation
The system SHALL use a revision-pinned separately deployed QuantumNous New API service as the default AI gateway for new installations and SHALL preserve its repository, release, license, reviewed Star count and review date as public supply-chain provenance.

#### Scenario: Default gateway stack is deployed
- **WHEN** an operator starts the documented default infrastructure profile
- **THEN** the pinned New API release starts with separate persistent gateway data and exposes a health-checked administration and API service without linking AGPL code into the BudgetLoop process

#### Scenario: Upstream source is inspected
- **WHEN** an operator audits bundled gateway dependencies
- **THEN** the canonical New API source at the recorded revision and its AGPL-3.0 license are available under the vendor directory and no moving `latest` reference is required to identify the deployed release

### Requirement: Mainstream protocol and custom upstream compatibility
The default gateway SHALL provide OpenAI Chat Completions, OpenAI Responses, Claude Messages and Gemini-compatible protocol surfaces plus legally authorized custom upstream channels through New API rather than BudgetLoop-owned protocol conversion code.

#### Scenario: Client uses a supported native protocol
- **WHEN** an authenticated gateway client sends a valid request to a supported OpenAI, Claude or Gemini surface
- **THEN** New API performs the configured protocol routing or conversion and BudgetLoop does not translate the request itself

#### Scenario: Operator adds a custom provider
- **WHEN** an operator configures an authorized custom upstream and model mapping in the New API console
- **THEN** BudgetLoop can address the resulting gateway model alias without receiving or storing the upstream credential

### Requirement: Typed replaceable gateway configuration
BudgetLoop SHALL select exactly one typed gateway mode from New API, legacy LiteLLM or an operator-supplied compatible endpoint and SHALL resolve gateway URL, server-side token, console URL and purpose-model aliases from server configuration.

#### Scenario: New API is configured
- **WHEN** the required New API URL, gateway token and recommendation alias are present
- **THEN** the control plane reports the gateway as configured and uses its OpenAI-compatible surface for bounded internal recommendation calls

#### Scenario: Legacy deployment is upgraded
- **WHEN** only the existing LiteLLM URL and master key are configured
- **THEN** the system continues in explicit LiteLLM compatibility mode without copying or exposing the legacy key

#### Scenario: Configuration is incomplete
- **WHEN** a gateway mode lacks its required URL, key or recommendation model
- **THEN** health reporting identifies an actionable sanitized configuration reason and no remote recommendation request is attempted

### Requirement: Redacted gateway health and capabilities
The control plane SHALL expose an authenticated bounded gateway-status endpoint containing gateway type, configured and healthy state, supported protocol names, routing mode, source provenance and a safe console link without returning credentials, request headers or raw upstream errors.

#### Scenario: Gateway preflight succeeds
- **WHEN** the configured gateway responds successfully within the health timeout
- **THEN** the status endpoint reports healthy state and beginner-readable capabilities without returning provider secrets or channel configuration

#### Scenario: Gateway preflight fails
- **WHEN** the gateway times out, rejects authentication or is unreachable
- **THEN** the status endpoint reports unavailable state and a stable sanitized reason code while logs omit tokens and prompt content

### Requirement: Gateway-native auditable routing
The system SHALL use New API's model mapping, channel priority, weighted selection, retry and rate-limit behavior for provider routing and SHALL NOT perform an additional LLM call solely to select another model.

#### Scenario: Multiple channels serve one purpose alias
- **WHEN** New API has multiple authorized channels mapped to the configured recommendation alias
- **THEN** New API applies its configured native routing and retry policy while BudgetLoop records only the stable purpose alias and gateway result facts

#### Scenario: Gateway routing exhausts eligible channels
- **WHEN** all eligible channels fail or are rate-limited
- **THEN** the gateway request fails within configured bounds and BudgetLoop applies the caller-specific fail-closed or local-fallback policy without silently changing gateway type

### Requirement: Server-side secret boundary
Gateway and upstream credentials SHALL remain in server-side configuration or the New API credential store and SHALL NOT be persisted in BudgetLoop business tables, returned by BudgetLoop APIs, embedded in browser bundles or written to logs.

#### Scenario: Public configuration is serialized
- **WHEN** the frontend requests gateway status or recommendation provenance
- **THEN** the response contains no API key, authorization header, provider credential or reversible secret fragment

#### Scenario: Recommendation request fails
- **WHEN** an upstream exception contains a URL, header or token-like value
- **THEN** the client maps it to a stable public failure code and does not include the raw exception in the API response
