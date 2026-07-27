## Why

An Agent Team can remain in `PLANNING` while its OpenHands workspace never becomes reachable. The worker currently retries a failed health endpoint until the startup timeout without publishing an observable stage, and the operator cannot tell whether work is queued, provisioning, or irrecoverably blocked.

## What Changes

- Make workspace startup failures fail closed with an actionable session workspace error and a terminal run outcome; a failed agent-server health check must not leave a session indefinitely planning.
- Surface real startup stages, elapsed waiting time, a visible activity mark, and workspace errors in the Agent Team workspace. The display will derive only from persisted run, workspace, and event state.
- Document the public execution and frontend behavior for startup, recovery, and failure feedback.
- Replace the mixed-language README with an English-first README and a separately selectable Simplified Chinese README, using familiar mature open-source project conventions while retaining accurate project setup and security guidance.

## Capabilities

### New Capabilities

- `session-startup-feedback`: Truthful, accessible progress and failure feedback for an Agent Team session while its workspace and agent are starting.

### Modified Capabilities

- `agent-server-execution-synchronization`: A server workspace startup failure must be bounded, recorded, and transitioned to an actionable terminal outcome.
- `isolated-session-workspaces`: Work-session workspace state must reflect provisioning failure rather than remain pending or provisioning.
- `frontend-experience-system`: Primary execution surfaces must present live startup feedback and recovery guidance in addition to generic loading states.

## Impact

- Affects the Python workspace manager/orchestrator and their pytest coverage; no provider credentials or new external services are exposed.
- Affects the Agent Team workspace UI, its TypeScript tests, and the existing container-detail response data it already polls.
- Does not change budget enforcement, direct-folder access rules, database schema, or introduce a migration. It only makes existing persisted lifecycle state visible and guarantees it converges on startup failure.
- Documentation changes affect `README.md` and a new `README.zh-CN.md`; no runtime behavior is implied by documentation alone.
