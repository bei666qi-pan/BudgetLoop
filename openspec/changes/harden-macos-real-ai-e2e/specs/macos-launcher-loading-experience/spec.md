## ADDED Requirements

### Requirement: Observable native web handoff
The macOS launcher SHALL keep the transition from service readiness to rendered Web UI observable, and SHALL not represent an empty or unfinished native web surface as a successful ready state.

#### Scenario: Services are healthy but WebKit is still loading
- **WHEN** Docker health checks pass and the native main-frame navigation has not yet completed
- **THEN** the window continues to show a plain-language loading state rather than a blank content area

#### Scenario: WebKit handoff fails persistently
- **WHEN** the native web navigation retry policy is exhausted
- **THEN** the window exposes the failed step, a sanitized explanation, and accessible retry and exit actions without relying on color alone
