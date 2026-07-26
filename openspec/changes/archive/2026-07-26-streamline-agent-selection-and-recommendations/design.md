## Context

The home draft service already calls a bounded OpenAI-compatible recommendation endpoint before its deterministic catalog matcher. In the local Sangfor profile, the gateway health probe succeeds and real execution completes, but a reproduced draft call returns `fallback_reason=timeout` at approximately 8 seconds: `GatewayClient.recommend()` shares the short generic read timeout even when `reasoning_effort=max` and 65,536-token thinking are enabled. The UI then promotes this implementation fallback into a large full-width card.

Engine metadata and adapters already come from a typed registry whose pinned sources exceed 10k reviewed GitHub stars: OpenHands (82,021), OpenAI Codex (101,301), and Gemini CLI (106,162). We will reuse those adapters and their runtime preflight rather than add another routing layer. The interaction hierarchy follows the restrained composer/progressive-disclosure direction used by the vendored OpenHands chat input and Google Gemini CLI, while retaining BudgetLoop's existing light-blue design tokens and page structure.

Task deletion is not currently modeled. Task-owned rows use run foreign keys without database cascades, and Agent Team sessions reference their tasks, so a blind ORM delete would be unsafe. PostgreSQL remains the only business source of truth and deletion must explicitly distinguish standalone task history from team-owned sessions.

## Goals / Non-Goals

**Goals:**

- Let reasoning-enabled recommendation complete inside a separate, bounded planning timeout and expose sanitized failure provenance only after an actual failure.
- Derive a stable recommended engine from server-owned task classification while letting an explicit operator selection override it.
- Present OpenHands, Codex, and Gemini CLI in one concise control and enforce registry preflight without silent engine substitution.
- Reduce visible implementation detail while preserving accessible provenance, budgets, approval, and permission facts on demand.
- Delete one eligible terminal standalone task and its database-owned run history only after explicit confirmation.
- Provide IME-safe Enter submission and an accessible BudgetLoop-logo planning/creation animation.

**Non-Goals:**

- Installing or authenticating an unavailable CLI engine, automatically routing to Gemini CLI, adding an AI router, or bypassing engine preflight.
- Deleting active runs, Agent Team containers/sessions, external workspaces/worktrees, provider data, or global infrastructure state.
- Changing budget settlement, approval enforcement, folder authorization, provider-key boundaries, or the application's information architecture.

## Decisions

### 1. Use an inference-aware recommendation timeout, not health as a success proxy

`GatewayClient.recommend()` will use a dedicated bounded read timeout. For ordinary models it keeps the configured bound; reasoning/thinking profiles receive a longer capped window suitable for structured planning. Connect, write, payload, response-size, and schema bounds remain unchanged. Logs retain only source, duration, status class, model alias, and sanitized fallback code.

Alternative considered: treat a healthy `/models`/validation probe as proof that recommendation succeeded. Rejected because health proves reachability, not completion. Alternative considered: remove the timeout. Rejected because the local fallback must remain a bounded recovery path.

### 2. Server derives `task_kind` and recommended engine; the browser owns explicit choice

The draft response adds a bounded public `task_kind` (`coding` or `general`) and returns `recommended_engine`. Classification is deterministic from the trusted selected preset category plus a small documented coding-signal set; software and game-development presets are coding. This works for both AI and local recommendation and does not require another model call. The default rule is:

1. Explicit operator engine selection: preserve it across follow-up draft refinement and send it in creation.
2. No explicit selection and `task_kind=coding`: Codex.
3. No explicit selection and `task_kind=general`: OpenHands.

Gemini CLI is available for explicit selection only. Registry preflight remains authoritative: unavailable options are disabled with a short reason; the server rejects unavailable selections and never silently substitutes another engine. OpenHands remains the API compatibility default for legacy callers that omit all new conversational fields.

Alternative considered: ask AI to choose an engine. Rejected because engine choice is a predictable product policy and AI availability must not change it. Alternative considered: introduce semantic AI routing. Rejected because two task classes and an explicit selector do not justify another control plane or dependency.

### 3. One compact primary review with progressive disclosure

The ready state keeps the title/goal, selected team, engine selector, folder access, and primary create action visible. Role topology, per-role budgets, aggregate details, gateway metadata, and fallback diagnostic move under semantic disclosure controls. AI success appears as quiet supporting text; local fallback appears as a compact neutral status and optional detail, not a large bordered warning.

This preserves transparent behavior without forcing beginners to interpret LangGraph, aliases, token allocation, or gateway internals. Existing form labels and validation stay available when expanded.

### 4. Delete terminal standalone task history transactionally

Add `DELETE /api/tasks/{task_id}`. It returns 404 for unknown IDs and 409 when a task is team-owned or any run is non-terminal. For an eligible task, the service deletes run-owned relational rows in dependency order, then runs and the task, in one transaction. External artifact blobs and workspace files are not removed in this change; database artifact references disappear with their owning rows and a later artifact-retention job may collect unreferenced blobs.

The recent-task row exposes a menu/delete control, a confirmation dialog naming the task, pending feedback, and optimistic removal only after a successful response. This avoids destructive row clicks and accidental deletion.

Alternative considered: soft delete. Rejected because it requires a schema migration, filtering changes across APIs, and retention semantics beyond the user's history-removal request. Alternative considered: cascade every task relationship in the schema. Rejected because team ownership makes a global cascade too broad.

### 5. Animate the existing vector mark and preserve keyboard/accessibility semantics

A shared `BudgetLoopActivityMark` composes the existing vector logo with two lightweight orbit elements and CSS transforms on wrapper elements, avoiding an animation dependency and avoiding expensive SVG path animation. It announces a concise `role=status` label; `prefers-reduced-motion` renders a gentle opacity state without orbiting.

The composer treats Enter as submit only when not composing, without Shift, with non-empty content, and while idle. Shift+Enter remains a newline; repeated Enter while busy is ignored. Form submission and the send button call the same handler.

## Risks / Trade-offs

- [Maximum-effort model can still exceed the longer bound] → keep a clear sanitized timeout code, preserve the draft input, and fall back deterministically; record duration for tuning without logging prompts or keys.
- [Codex is the recommended coding engine but its local runtime is unavailable] → show the policy recommendation and disabled readiness reason, prevent confirmation, and let the operator explicitly choose an available engine; never claim Codex ran.
- [Preset-based classification can misclassify mixed work] → make the selector always visible, preserve explicit choice through refinement, and keep the classification public and testable.
- [Manual dependency deletion misses a new run-owned table] → centralize deletion order, cover all current foreign keys with integration tests, and fail/rollback the transaction on constraint errors.
- [Motion distracts or causes discomfort] → keep the mark small, use transform/opacity only, and honor reduced-motion.

## Migration Plan

1. Ship additive draft response fields and the deletion endpoint; existing clients continue using OpenHands when they omit engine selection.
2. Update the home client and tests to consume the new fields and expose the controls.
3. Rebuild the local app stack and verify the real Sangfor draft path reports `source=ai` under maximum reasoning settings.
4. Rollback is code-only: older clients ignore additive fields, and removing the DELETE route restores prior behavior. No schema rollback is required.

## Open Questions

None. Runtime installation/authentication for currently unavailable CLI engines remains a separately visible readiness concern rather than being hidden inside this UI change.
