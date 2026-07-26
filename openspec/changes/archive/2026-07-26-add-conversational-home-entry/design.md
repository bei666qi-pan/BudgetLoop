## Context

BudgetLoop currently splits the beginner journey across three product surfaces: `/` is a task dashboard, `/new` is a detailed single-task form, and `/containers/new` recommends and creates Agent Teams. The backend already has the important primitives this change needs: bounded AI-first preset recommendation with a deterministic LangGraph fallback, catalog-owned role and budget definitions, idempotent transactional team creation, hard approvals/budgets, and run-level `model_config`. The active `mac-launcher-folder-access` change also implements the host folder picker bridge and the `folder_access` policy/enforcer path for single tasks.

The design therefore composes those capabilities instead of introducing another agent framework, task store, or sandbox. PostgreSQL remains authoritative only after confirmation; an unconfirmed setup draft is short-lived browser/API state and cannot consume execution budget or mutate a project.

Open-source lineage is deliberately reused from the repository's 2026-07-25 review (`openspec/changes/archive/2026-07-25-add-smart-agent-team-presets/research.md`): Codex (`openai/codex`, 101,301 reviewed stars, Apache-2.0) and OpenHands (`OpenHands/OpenHands`, 82,021 reviewed stars, MIT core) were active, unarchived, and already pinned under `vendor/agent-engines/`. Conversation-first composition follows the bounded composer/start-conversation separation in OpenHands (`frontend/src/components/features/chat/components/chat-input-container.tsx` and `frontend/src/hooks/mutation/use-unified-start-conversation.ts`). Permission semantics follow Codex's `SandboxMode` (`codex-rs/protocol/src/config_types.rs:86-96`), declarative `FileSystemSandboxPolicy::workspace_write` (`codex-rs/protocol/src/permissions.rs:570-621`), enforcement translation (`codex-rs/sandboxing/src/manager.rs`), and explicit approval overlay (`codex-rs/tui/src/bottom_pane/approval_overlay.rs`). Existing LangGraph/CrewAI/MetaGPT-derived team topology remains as documented by the archived preset change.

## Goals / Non-Goals

**Goals:**

- Make plain-language goal entry the first and most obvious action on the home page for both new and returning operators.
- Produce a complete, explainable, server-validated team setup with safe defaults and no required framework, role, budget, or permission expertise.
- Let the operator review and optionally edit the outcome in one compact confirmation surface, then create the entire team through the existing atomic/idempotent contract.
- Keep AI recommendation, folder authorization, hard budgets, and execution approval visibly distinct so a model can never grant itself access or silently start work.
- Reuse the active Codex-derived folder-access implementation for every team run and fail closed when the requested workspace cannot be provisioned.
- Preserve recent-work discovery, advanced forms, preset browsing, manual teams, mobile accessibility, and trustworthy degraded states.

**Non-Goals:**

- A general-purpose persistent chatbot, arbitrary tool calling from the home composer, or storage of unconfirmed transcripts in PostgreSQL.
- Free-form AI-generated roles, tools, engines, budgets, or permission policies outside the trusted catalog and server bounds.
- A new sandbox, permission enum, orchestration runtime, provider setup flow, database table, or background planning worker.
- Automatic git merge, automatic budget increase, cloud folder access, or changes to run/report supervision.

## Decisions

### 1. Home is an intake workspace, not a decorative chat skin

`/` becomes a vertically ordered workspace: a concise outcome-oriented heading, a large multi-line composer with a few example prompts, the current draft/clarification region, and then the existing recent-task dashboard in a quieter secondary section. Returning operators keep search, filters, and direct run continuation; the `/new` and `/containers/new` links remain available as advanced paths.

The initial request is single-turn by default. If the server can apply safe defaults it returns a ready draft immediately. Follow-up text updates the current draft, but the UI asks a clarification only when a required fact cannot be derived safely; it never forces the user to choose a framework, team topology, budget strategy, or folder mode. This preserves the ease of a composer while avoiding the cost, persistence, and navigation complexity of a general chat system.

Alternative considered: redirecting the composer to the current Agent Team form. Rejected because it leaves the user responsible for interpreting and completing the form, contrary to the one-confirmation goal.

### 2. A stateless, catalog-constrained draft endpoint

Add `POST /api/task-drafts` with a bounded request containing `message` and an optional previous public draft for follow-up refinement. The response has a versioned `TaskSetupDraft`:

- normalized project title, goal, acceptance criteria, and shared context;
- selected trusted `preset_id`/`preset_version`, public match reason/signals, catalog-owned roles and tasks;
- catalog-owned starter budgets, approval enabled, start-immediately intent, and available execution-engine facts;
- `ready` or `needs_input` state with at most two concise public clarification prompts;
- recommendation provenance (`ai` or `local_fallback`), model alias when applicable, duration, and sanitized fallback code.

The model may propose only bounded text fields and identifiers from the server-supplied trusted catalog. The server resolves the actual preset, roles, tasks, budgets, engine availability, approval default, and activation graph. Unknown keys, oversized content, unknown preset IDs, role invention, invalid numeric values, or malformed output are rejected and replaced by the deterministic local recommendation plus catalog defaults. Hidden reasoning is neither requested nor returned.

Alternative considered: persisting a `task_drafts` table. Rejected because the draft is not business state, does not need cross-device recovery in this scope, and would create cleanup/privacy/migration work before the user has consented to create anything.

### 3. AI planning and operator-controlled permissions are separate state domains

`TaskSetupDraft` does not contain an AI-selected host path, writable mode, acknowledgement, or approval disablement. The frontend owns a separate `WorkspaceAccessSelection`, initialized to `{folder_access: "isolated", project_dir: null}` and `require_approval: true`. A follow-up AI response cannot overwrite it.

Selecting writable access is a direct operator action. In the native app, the existing macOS bridge opens the system folder picker; in browser-only development an explicitly labelled advanced absolute-path input remains available. The confirmation card shows the canonical path, “Agent 可直接读写（含 .git）”, per-session worktree behavior, and the high-risk acknowledgement beside the final action. Changing the path or mode clears the acknowledgement. Merely mentioning a path in the prompt never authorizes it.

Alternative considered: letting the planner infer `full_access` when the user says “修改这个项目”. Rejected because natural-language intent is not a reliable authorization boundary and conflicts with Codex's explicit policy/approval separation.

### 4. One review card is the commit boundary

The ready state renders one semantic review card with five beginner-readable groups: “要完成什么”, “谁来完成”, “怎样验收”, “可用资源”, and “文件与安全”. The collapsed/default view shows the chosen team, role count, aggregate token/call/cost caps, approval-on state, folder mode/path, and recommendation provenance. Each group has an edit action; advanced role/budget controls reuse the existing team components under progressive disclosure.

The primary action is “确认并启动”. It is enabled only when the draft is server-valid, required engines are available, folder rules are satisfied, and writable access is acknowledged. Confirmation sends one idempotent request to the extended `POST /api/work-containers/from-preset`; no draft-generation request creates records or dispatches workers. A retained idempotency key makes retry safe, and client validation is repeated by the server.

Alternative considered: a four-step wizard. Rejected because safe defaults and one complete review surface provide the same control with much lower beginner friction.

### 5. Preset team creation gains additive folder-access fields

Extend `CreateTeamFromPresetRequest` with:

- `folder_access: Literal["isolated", "full_access"] = "isolated"`;
- `project_dir: str | None = None`;
- `full_access_acknowledged: bool = false`.

Move canonical path validation from `api/tasks.py` into a shared backend policy module and use it for both single-task and team creation. `full_access` requires a valid selected path, acknowledgement, and `default_workspace_policy=worktree`; the server rejects rather than silently rewriting an unsafe combination. For each created session, the confirmed fields are copied into `run.model_config` alongside the selected execution engine. The applied snapshot records the policy and canonical path for audit without credentials or prompt internals.

With writable host access, each team session uses the existing server-generated branch/worktree mechanism so concurrent agents do not intentionally share one working directory. `WorkspaceManager.provision()` remains the only Docker mount enforcer. Mount, Git, or worktree failures leave the run failed with an actionable workspace error; they never downgrade to an isolated volume or direct shared-folder execution.

Alternative considered: adding a third folder mode in this change. Rejected because the active folder-access OpenSpec already establishes the product vocabulary and enforcement semantics; expanding it here would overlap an unfinished change.

### 6. Recommendation degrades without blocking creation

The planner reuses the configured gateway client, timeout/size bounds, strict JSON parsing, trusted catalog lookup, and public provenance pattern from `team_presets.ai_recommend`. When AI is disabled, unconfigured, times out, or returns invalid content, the deterministic LangGraph recommendation produces the preset and server defaults produce a complete draft. The UI labels the fallback truthfully but treats it as usable, not as a creation failure.

Structured logs include request ID, source, gateway type, model alias, duration, status class, fallback code, chosen preset ID, and validation outcome. They exclude prompt text, project paths, credentials, hidden reasoning, and the acknowledgement value. API/worker failures preserve composer and draft state for retry.

### 7. Accessible responsive states use the existing system

The composer is a labelled form with submit semantics, keyboard shortcut help, visible focus, and a non-color loading state. Status changes use an `aria-live` region; clarification prompts and errors use semantic headings/alerts. On narrow screens the review groups stack and the final summary/action stays reachable without covering editable content. Reduced-motion rules and existing design tokens/primitives remain authoritative.

The UI has explicit empty, planning, needs-input, ready, confirming, retryable-error, and created states. It never displays simulated agents, budgets, paths, or AI success before the corresponding API facts exist.

## Risks / Trade-offs

- [A fluent draft may look like a promise of correctness] → Label it “建议配置”, expose acceptance criteria and source, and keep all fields reviewable before confirmation.
- [Fallback-generated acceptance criteria can be generic] → Keep the user's goal intact, use preset task outputs as bounded defaults, and make criteria directly editable.
- [Full-access Agent Teams can modify git metadata or race during provisioning] → Require worktrees, unique server-generated identifiers, fail-closed Git setup, targeted concurrency tests, and a prominent `.git` warning.
- [A browser cannot prove that a typed server path was selected by the local user] → Prefer the native picker, label manual path entry as advanced/local-only, and retain server allow/deny validation; do not claim OS authorization in browser mode.
- [Composer prominence can bury active work] → Keep attention counts and recent tasks immediately below the intake area with direct continuation actions.
- [Two creation surfaces can drift] → Extract shared draft/review types and reuse existing preset, role, budget, engine, validation, and API helpers rather than duplicating catalog logic.
- [Draft endpoint adds LLM latency] → Bound the request, show immediate planning feedback, allow cancellation/replacement, and fall back deterministically on timeout.

## Migration Plan

1. Finish or rebase on `mac-launcher-folder-access` so the shared folder policy and native bridge are authoritative.
2. Extract shared path/policy validation without changing the existing single-task API behavior; add unit coverage before extending team creation.
3. Add the stateless draft service/endpoint and backend tests for AI, invalid-output fallback, content bounds, provenance, and no database side effects.
4. Add the folder fields to preset team creation and propagate them to run configuration/snapshots; test idempotency, rollback, worktree enforcement, and fail-closed provisioning.
5. Add shared frontend intake/review components, then compose the new home hierarchy while retaining the task dashboard and advanced routes.
6. Verify desktop/mobile keyboard and screen-reader states, frontend tests/build, backend tests, and one native-picker end-to-end run in isolated and full-access modes.

Rollback is additive: restore the previous home route and stop calling the draft endpoint, then ignore the optional team-creation fields. Existing tasks/containers remain valid because the endpoint defaults to isolation and all persistence uses existing JSONB fields.

## Open Questions

None for the initial implementation. Persistent draft history, cloud repositories, extra permission modes, and automatic merge remain separate changes.
