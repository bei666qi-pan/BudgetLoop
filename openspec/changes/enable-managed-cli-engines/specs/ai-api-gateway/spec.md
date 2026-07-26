## MODIFIED Requirements

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

### Requirement: Server-side secret boundary
Gateway and upstream credentials SHALL remain in server-side configuration or the New API credential store and SHALL NOT be persisted in BudgetLoop business tables, returned by BudgetLoop APIs, embedded in browser bundles, written to logs or injected into an Agent process.

#### Scenario: Public configuration is serialized
- **WHEN** the frontend requests gateway status, recommendation provenance or execution-engine readiness
- **THEN** the response contains no API key, authorization header, runtime capability, provider credential or reversible secret fragment

#### Scenario: Managed engine request is forwarded
- **WHEN** Codex or Gemini CLI calls BudgetLoop with a valid runtime capability
- **THEN** BudgetLoop removes that capability from the upstream request, injects the gateway credential only on the server-to-gateway hop and returns no credential material

#### Scenario: Recommendation or managed request fails
- **WHEN** an upstream exception contains a URL, header or token-like value
- **THEN** the client maps it to a stable public failure code and does not include the raw exception in the API response

## ADDED Requirements

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
