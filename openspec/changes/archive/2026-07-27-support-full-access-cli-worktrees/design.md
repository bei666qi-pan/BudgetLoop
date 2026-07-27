## Context

`LocalWorkspaceManager` provides persistent, per-run workspaces for Codex and Gemini CLI inside the worker container. It correctly rejects direct host-folder access, but Agent Team creation currently permits the incompatible combination. The OpenHands server engine already provisions the selected host folder through a Docker mount and creates the required server-owned worktree.

## Goals / Non-Goals

**Goals:**

- Ensure every full-access team uses the engine that can mount the confirmed host folder and create its server-owned worktree.
- Prevent incompatible CLI/full-access requests before any task or run is stored.
- Preserve isolated CLI workspace behavior and engine selection.

**Non-Goals:**

- Do not add a shared-root mode, change Docker/OpenHands provisioning, or mount arbitrary host paths into the worker container.
- Do not change budget accounting, CLI runtime credentials, or external deployment configuration.

## Decisions

### Use OpenHands for direct project access

For `folder_access=full_access`, Agent Team creation accepts only an execution engine with server transport. The current supported engine is OpenHands, whose workspace manager bind-mounts the selected host project and creates a server-owned worktree. CLI engines continue to operate only in their worker-local isolated workspace.

Mounting an arbitrary project into the long-running worker was rejected because Docker mounts are fixed at worker startup and would broaden access. Copying the project into the CLI root was rejected because it would silently downgrade direct-write mode.

### Validate before creation and constrain the UI

The API inspects the selected default and role override engines before storing a container. Any CLI engine in a full-access team receives a 422 response naming the supported engine. The guided setup automatically selects OpenHands and removes incompatible choices as soon as direct access is selected. This prevents a zero-iteration failed run rather than routing it to an isolated workspace.

## Risks / Trade-offs

- [An API client bypasses the UI and selects a CLI engine] → API validation rejects it before creation.
- [OpenHands is unavailable] → Existing preflight returns an actionable availability error; no CLI fallback is attempted.
