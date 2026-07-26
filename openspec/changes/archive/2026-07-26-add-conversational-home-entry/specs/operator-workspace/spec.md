## ADDED Requirements

### Requirement: Conversational home hierarchy
The operator workspace SHALL make a plain-language task composer the primary home-page action while retaining task status discovery, search, filtering, and direct continuation as a secondary recent-work region.

#### Scenario: Home page has no tasks
- **WHEN** the task API returns an empty collection
- **THEN** the home page leads with example-assisted goal entry and does not require the operator to navigate to a separate form before describing work

#### Scenario: Home page has existing tasks
- **WHEN** the task API returns one or more tasks
- **THEN** the composer remains prominent and the existing status summary, search, filters, and run actions remain reachable below it

#### Scenario: Operator prefers advanced setup
- **WHEN** the operator chooses manual task configuration, preset browsing, or empty-container creation
- **THEN** the workspace exposes the existing advanced route without discarding the home draft or mislabelling it as started

### Requirement: Attention-preserving home state
The home page SHALL keep actionable existing work visible while a new setup draft is idle, planning, ready, or in error and SHALL not let the creation surface hide tasks that require approval or recovery.

#### Scenario: Existing run needs attention
- **WHEN** a returned task has a waiting-approval, failed, or other attention status
- **THEN** the recent-work region exposes its status and direct continuation action even when a new draft is present

