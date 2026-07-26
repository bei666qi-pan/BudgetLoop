## ADDED Requirements

### Requirement: Aggregate metering metrics
The run detail page SHALL present an observability panel that aggregates the run's LLM calls into at minimum: total, prompt, completion, reasoning, and cache token counts; summed estimated cost; average call duration and average time-to-first-token when reported; call success rate by `request_status`; and cache-hit rate over calls that report cache fields. Aggregates SHALL be derived from the run's real `llm-calls` API data and SHALL update on the same refresh cycle as the rest of the run page.

#### Scenario: Run with completed LLM calls
- **WHEN** a run has one or more recorded LLM calls with token, duration, and status fields
- **THEN** the panel displays aggregate token, cost, latency, and success metrics computed from those calls without requiring a separate fetch

#### Scenario: Metrics refresh while the run is live
- **WHEN** a new LLM call is recorded during an active run's poll cycle
- **THEN** the aggregate metrics reflect the new call on the next refresh without operator interaction

### Requirement: Consumption trend visualization
The observability panel SHALL visualize cumulative token consumption over time and SHALL visualize cumulative estimated cost over time when cost data is available, using the shared chart primitives with palette-consistent colors.

#### Scenario: Sufficient call history
- **WHEN** the run has two or more calls with usable timestamps
- **THEN** the panel renders cumulative token and cost trend charts derived from per-call data

#### Scenario: Insufficient history
- **WHEN** the run has fewer than two calls with usable timestamps
- **THEN** the charts render the shared empty state rather than a misleading flat or fabricated line

### Requirement: Per-call metering detail
The observability panel SHALL expose per-call metering beyond the existing table by surfacing time-to-first-token, reasoning and cache token counts, provider, retry count, and token source when the API reports them, and SHALL attribute each call to its model and call kind.

#### Scenario: Call reports extended metering
- **WHEN** an LLM call includes `ttft_ms`, cache or reasoning token fields, or a non-default retry count
- **THEN** the panel displays those values for that call with readable labels

#### Scenario: Per-model breakdown
- **WHEN** calls span more than one model or call kind
- **THEN** the panel breaks down token consumption per model and per call kind so the operator can attribute spend

### Requirement: Honest partial metering data
The observability panel SHALL label unavailable or unconfigured metering values explicitly and SHALL NOT render them as zeroes, fabricated numbers, or misleading chart lines.

#### Scenario: Cost is not configured
- **WHEN** every recorded call reports a null estimated cost
- **THEN** the panel labels cost as unavailable (价格未配置) and omits or empty-states the cost trend instead of plotting zero

#### Scenario: Sparse optional fields
- **WHEN** individual calls lack optional fields such as `ttft_ms` or cache token counts
- **THEN** those cells are marked as not reported rather than filled with zeros
