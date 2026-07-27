## Why

Full-access Agent Teams can select a CLI engine such as Codex, but a CLI process runs inside the worker container and cannot safely access an arbitrary host folder. The current creation flow accepts that incompatible combination, so every session fails before its first iteration.

## What Changes

- Restrict full-access Agent Teams to the OpenHands server engine, which already provisions a Docker workspace with the selected host project mounted and a server-owned worktree.
- Switch the guided setup UI to OpenHands when an operator selects direct project access, and hide incompatible CLI choices for that mode.
- Reject API requests that combine full access with a CLI engine before tasks or runs are created.
- Keep CLI engines available for isolated workspaces.

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `isolated-session-workspaces`: Full-access worktree isolation must apply to supported CLI execution engines as well as Docker workspaces.
- `managed-cli-engine-runtime`: Managed CLI engines must remain unavailable for direct host-folder access.

## Impact

- Affects Agent Team creation validation, the guided setup UI, and focused API/UI tests.
- No database migration, external dependency, budget-accounting, or infrastructure change.
- Non-goal: this does not add shared-root execution, change selected-folder authorization, or retrofit a host-folder mount into a CLI worker process.
