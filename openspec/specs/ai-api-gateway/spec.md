# ai-api-gateway Specification

## Purpose

Define the replaceable, separately deployed AI gateway boundary, protocol
compatibility, routing ownership, health transparency and server-side secret
handling used by BudgetLoop.
## Requirements
### Requirement: Maintained open-source gateway foundation
The system SHALL use a revision-pinned separately deployed QuantumNous New API service as the default AI gateway for new installations and SHALL preserve its repository, release, license, reviewed Star count and review date as public supply-chain provenance.

#### Scenario: Default gateway stack is deployed
- **WHEN** an operator starts the documented default infrastructure profile
- **THEN** the pinned New API release starts with separate persistent gateway data and exposes a health-checked administration and API service without linking AGPL code into the BudgetLoop process

#### Scenario: Upstream source is inspected
- **WHEN** an operator audits bundled gateway dependencies
- **THEN** the canonical New API source at the recorded revision and its AGPL-3.0 license are available under the vendor directory and no moving `latest` reference is required to identify the deployed release

### Requirement: Mainstream protocol and custom upstream compatibility
The default gateway SHALL provide OpenAI Chat Completions, OpenAI Responses, Claude Messages and Gemini-compatible protocol surfaces plus legally authorized custom upstream channels through New API rather than BudgetLoop-owned protocol conversion code, and the deployed pinned New API release SHALL expose every protocol advertised as locally available.

#### Scenario: Client uses a supported native protocol
- **WHEN** an authenticated gateway or scoped managed-runtime client sends a valid request to a supported OpenAI, Claude or Gemini surface
- **THEN** New API performs the configured protocol routing or conversion and BudgetLoop does not translate the request itself

#### Scenario: Deployed gateway lacks an advertised route
- **WHEN** a pinned New API image does not expose a required native route or returns its browser shell for an API request
- **THEN** the corresponding engine remains unavailable and deployment verification fails instead of treating an HTTP 200 shell response as protocol readiness

#### Scenario: Local configuration bypasses New API
- **WHEN** BudgetLoop's local gateway URL points directly at an upstream compatible-provider endpoint instead of the configured New API instance
- **THEN** native protocol readiness fails and the operator is directed to route the provider through New API rather than adding protocol conversion to BudgetLoop

#### Scenario: Operator adds a custom provider
- **WHEN** an operator configures an authorized custom upstream and model mapping in the New API console
- **THEN** BudgetLoop can address the resulting gateway model alias without receiving or storing the upstream credential

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
Gateway and upstream credentials SHALL remain in server-side configuration, the New API credential store or an approved OS secret store and SHALL NOT be persisted in BudgetLoop business tables, generated project files, returned by BudgetLoop APIs, embedded in browser bundles or written to logs; managed applications SHALL receive only short-lived scoped BudgetLoop capabilities, and Agent processes SHALL never receive upstream gateway credentials.

#### Scenario: Public configuration is serialized
- **WHEN** the frontend requests gateway status, recommendation provenance or execution-engine readiness
- **THEN** the response contains no API key, authorization header, runtime capability, provider credential or reversible secret fragment

#### Scenario: Generated application is provisioned
- **WHEN** a managed AI application starts in a BudgetLoop workspace
- **THEN** the real upstream credential remains server-side and only a bounded scoped capability is provided to the child process in memory

#### Scenario: Managed engine request is forwarded
- **WHEN** Codex or Gemini CLI calls BudgetLoop with a valid runtime capability
- **THEN** BudgetLoop removes that capability from the upstream request, injects the gateway credential only on the server-to-gateway hop and returns no credential material

#### Scenario: Recommendation or managed request fails
- **WHEN** an upstream exception contains a URL, header or token-like value
- **THEN** the client maps it to a stable public failure code and does not include the raw exception in the API response

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

### Requirement: Bounded native-protocol managed runtime
BudgetLoop SHALL expose allowlisted Responses and Gemini generateContent/streamGenerateContent managed-runtime routes for one live run and allowed model, forward them through New API without protocol conversion, and meter them against the existing TaskRun budget.

#### Scenario: Responses stream is requested
- **WHEN** a valid runtime capability submits a bounded Responses request for its allowed model
- **THEN** BudgetLoop reserves budget, forwards the request to New API, streams the compatible response and settles usage without recording prompt or completion content

#### Scenario: Gemini content is requested
- **WHEN** a valid runtime capability submits a bounded Gemini generateContent or streamGenerateContent request whose path model matches the capability
- **THEN** BudgetLoop reserves budget, forwards the native request to New API with server-side gateway authentication and returns the native response or stream

#### Scenario: Native runtime request violates policy
- **WHEN** the method, path, body size, run state, model, budget or capability is invalid
- **THEN** BudgetLoop rejects the request before contacting New API with a stable secret-free reason

#### Scenario: Successful stream omits usage
- **WHEN** a native stream completes successfully without parseable usage metadata
- **THEN** BudgetLoop conservatively settles the reserved estimate as consumed and records only bounded run/model/status facts

### Requirement: Agent execution respects the server-side secret boundary
The system SHALL keep gateway and upstream credentials in the control plane when configuring any agent-server execution. It SHALL use a scoped managed-runtime capability for the agent-server's model invocation and SHALL NOT write either credential class to a project file, database business record, browser payload, or log.

#### Scenario: Agent-server conversation is configured
- **WHEN** the worker creates an OpenHands agent-server conversation for a task run
- **THEN** its LLM configuration contains only the managed proxy URL, model alias, and run-scoped capability, never the configured upstream API key

#### Scenario: Runtime configuration is rejected
- **WHEN** the workspace cannot obtain a valid scoped capability
- **THEN** the worker does not substitute the upstream credential and exposes only a stable sanitized failure reason
