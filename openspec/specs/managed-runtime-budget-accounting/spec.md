# managed-runtime-budget-accounting Specification

## Purpose
TBD - created by archiving change prevent-managed-runtime-double-accounting. Update Purpose after archive.
## Requirements
### Requirement: Managed runtime usage has one settlement source
BudgetLoop SHALL count each managed-runtime upstream LLM request and its actual usage exactly once. The managed runtime proxy SHALL settle those requests, and the worker SHALL NOT add an additional synthetic call or duplicate the cumulative OpenHands usage when the same execution completes.

#### Scenario: Managed OpenHands execution completes
- **WHEN** an agent-server run makes multiple LLM requests through the managed runtime and returns cumulative usage metrics
- **THEN** the task budget's used calls and tokens equal the requests and usage settled by the proxy, while the observatory records the corresponding response metrics without settling them again

#### Scenario: Managed execution fails after some requests
- **WHEN** some managed-runtime requests have already settled before the agent execution fails
- **THEN** their committed usage remains counted once and the worker releases only its outstanding outer iteration reservation

### Requirement: Outer iteration reservation remains bounded and releasable
BudgetLoop SHALL retain the worker's outer iteration reservation while managed agent execution is in flight and SHALL release that reservation after execution or failure without altering the proxy-settled used totals.

#### Scenario: Managed iteration reaches observation
- **WHEN** the managed agent execution completes and observation data is persisted
- **THEN** the outer estimated reservation becomes zero and no extra used call or token amount is added

#### Scenario: Non-managed execution completes
- **WHEN** an execution transport does not use BudgetLoop's managed runtime proxy
- **THEN** the worker retains its existing reserve-and-settle accounting behavior
