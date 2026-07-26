## RENAMED Requirements

- FROM: `### Requirement: Local explainable team recommendation`
- TO: `### Requirement: AI-first explainable team recommendation`

## MODIFIED Requirements

### Requirement: AI-first explainable team recommendation
The system SHALL first use a bounded AI request through the configured gateway to rank only trusted built-in presets and SHALL validate all structured output against the local catalog; when AI is disabled, unconfigured, unavailable, timed out or invalid, it SHALL use the compiled local LangGraph recommendation graph and disclose the result source without failing the creation path.

#### Scenario: Healthy AI gateway recommends a known team
- **WHEN** the operator submits a valid goal while AI recommendation and its gateway model alias are healthy
- **THEN** the system returns up to three catalog-owned presets with bounded confidence, concise reasons, public matched signals and `ai` source provenance without returning hidden reasoning

#### Scenario: AI returns untrusted or malformed output
- **WHEN** the gateway response is malformed, oversized, duplicates identifiers or references a preset outside the trusted catalog
- **THEN** the system rejects the invalid AI result, runs the deterministic local graph and returns a sanitized local-fallback reason

#### Scenario: AI is unavailable
- **WHEN** AI recommendation is disabled or the gateway is missing credentials, unhealthy or exceeds its timeout
- **THEN** the local LangGraph graph returns usable recommendations and the response truthfully reports that no successful AI recommendation was used

#### Scenario: Goal matches a known domain locally
- **WHEN** the local fallback receives a goal with signals matching one or more catalog domains
- **THEN** the system returns up to three ranked presets with bounded confidence, matched public signals and a readable recommendation reason

#### Scenario: Goal has no strong local match
- **WHEN** the local fallback finds no useful catalog signal
- **THEN** the LangGraph conditional fallback routes to the generic project team, labels it as a safe fallback and still allows the operator to browse every preset

#### Scenario: Recommendation input is invalid
- **WHEN** the goal is blank, over the content bound or an optional preference is not recognized
- **THEN** the request is rejected with field-specific feedback before project text is sent to any external service
