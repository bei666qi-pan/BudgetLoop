## Context

BudgetLoop already persists isolated work containers and creates each runnable session as a standard Task, TaskRun, budget and phase set. The manual creation route deliberately creates an empty container, after which an operator must configure every session. The new experience must remove that setup burden without weakening recipient isolation, budget enforcement, approval gates or PostgreSQL authority.

Ten high-star open-source projects were reviewed in `research.md`. LangGraph is adopted directly for state-graph execution; CrewAI's YAML role/goal/task conventions and MetaGPT's SOP stages shape the portable preset files. BudgetLoop owns the control plane while OpenHands, Codex, Gemini CLI and OpenCode are interchangeable execution engines behind one adapter boundary. The selected desktop and mobile references are `concepts/concept-smart-team-presets-desktop.png` and `concepts/concept-smart-team-presets-mobile.png`.

## Goals / Non-Goals

**Goals:**

- Provide useful, versioned teams for common beginner scenarios with safe role, skill, budget, approval and workspace defaults.
- Recommend teams locally from a bounded goal and optional preferences, with readable match reasons and source attribution.
- Create the container and all initial sessions in one database transaction, with an idempotent request and an explicit start-now or start-later choice.
- Preserve the existing manual path and allow experienced operators to adjust roles, goals and bounded budgets before creation.
- Make preset provenance and the exact applied snapshot auditable after catalog versions change.

**Non-Goals:**

- Allowing any execution engine to replace PostgreSQL authority, BudgetLoop budgets/approvals, explicit Handoff semantics or workspace ownership.
- LLM-based recommendation, remote telemetry, hidden scoring rationale or provider-key setup.
- Implicit cross-session context, unrestricted group chat, auto-merge or automatic budget increases.
- A general marketplace or user-authored preset editor in this change.

## Decisions

### 1. CrewAI-compatible YAML presets with MetaGPT-style SOP stages

The backend will load reviewed immutable YAML presets using the same core declarative vocabulary promoted by CrewAI: agents have role, goal and backstory/private operating context; tasks have description, expected output and assigned agent. BudgetLoop extensions add safe budgets, skill labels, source metadata and workspace defaults. Each preset also defines ordered SOP stages inspired by MetaGPT, including parallel roles and review gates. The first catalog includes a generic project team plus software delivery, game development, business growth, product launch, brand content, market research, data analysis and customer support.

This is preferred over a proprietary Python-only schema because teams remain understandable and portable to the most widely adopted role/task model. It is preferred over a database-authored catalog because this change does not include preset administration and code-versioned YAML is easier to review and test. The backend still owns validation and instantiation.

### 2. LangGraph-backed deterministic recommendation

`POST /api/work-container-presets/recommend` invokes a compiled LangGraph `StateGraph` with normalize, classify, rank, explain and fallback nodes. Nodes operate on bounded typed state, score catalog signals and preference weights, and return the top three results. Confidence is a presentation score bounded between 55 and 95; reasons are assembled from matched public signal labels, not hidden chain-of-thought. When no useful signal matches, a conditional edge routes to the generic project preset.

Using LangGraph avoids creating a proprietary state-machine engine while keeping the recommendation instant, testable, offline and configuration-free. The API shape leaves room for a future provider-backed node, but such a change would need separate privacy and transparency requirements.

### 3. LangGraph activation plans adapt open-source topology to BudgetLoop

Each preset's SOP stages compile into a LangGraph activation graph. Invoking the graph yields ordered activation waves, required Handoff edges and review gates. BudgetLoop persists this applied graph in the snapshot and uses its activation waves when dispatching PENDING runs. Session execution remains engine-native behind BudgetLoop's adapter contract; the adapter maps open-source graph nodes to existing WorkSession/TaskRun identifiers instead of reimplementing an agent runtime.

### 4. BudgetLoop-owned execution-engine registry

BudgetLoop persists the selected engine id and engine-safe configuration with each Run while keeping all durable status, budget, approval and event transitions in the control plane. A typed registry exposes engine capabilities and command/server transport without importing engine-specific state models into core orchestration. `openhands` remains the compatibility default; `codex`, `gemini-cli` and `opencode` are opt-in per team or role.

The repository includes revision-pinned shallow source checkouts under `vendor/agent-engines/` plus a machine-readable manifest containing canonical repository, commit, reviewed stars, license and supported transport. Codex and Gemini CLI are Apache-2.0, OpenCode is MIT, and OpenHands core is MIT; OpenHands `enterprise/` is excluded because it carries separate terms. Runtime builds may use these local snapshots, while ordinary development can point adapters at already-installed binaries or services.

The adapter contract covers availability checks, conversation/session creation, one bounded step, public event normalization, pause/cancel and cleanup. Provider credentials remain explicitly engine-scoped. Selecting an unavailable engine produces a clear preflight error and never silently falls back to another engine.

### 5. Explicit atomic preset instantiation

`POST /api/work-containers/from-preset` accepts the preset/version, project facts, bounded role overrides, workspace policy and `start_immediately`. It requires an `Idempotency-Key`. The handler resolves and validates the preset, creates the container, sessions, Tasks, TaskRuns, budgets and phases in one transaction, and commits before any queue dispatch.

Queue dispatch remains post-commit because Dramatiq is not transactionally coupled to PostgreSQL. The response records per-run dispatch warnings without rolling back durable records. An idempotent retry returns the existing team rather than duplicating sessions.

For `start_immediately=false`, runs remain `PENDING` and are not dispatched. `POST /api/work-containers/{id}/start` explicitly dispatches eligible PENDING preset runs and is safe to retry. This is preferred over manufacturing an initial PAUSED state, which would violate current transition and conversation assumptions.

### 6. Persist provenance and applied snapshot

`work_containers` gains nullable `preset_id`, `preset_version`, `preset_snapshot` JSONB and `idempotency_key`. Manual containers leave them null. The snapshot contains only public applied template data and operator-approved overrides; it contains no transcript, credentials or hidden recommendation internals.

Snapshot persistence is preferred over looking up the latest catalog at read time because teams must remain auditable after presets evolve. A unique nullable idempotency key prevents duplicate team creation.

### 7. Beginner-first frontend with progressive disclosure

`/containers/new` loads the catalog once and defaults to Smart Recommendation. A debounced request runs only after a meaningful goal length, while the visible recommendation button remains available. Preset browsing uses category tabs and open list rows. Selection fills a single team preview; role and budget editing plus workspace details sit behind clear optional controls.

The primary action creates and starts. The secondary action creates without dispatch. Both use the same payload and show concrete in-flight/error feedback. The desktop preview becomes a sticky bottom action bar on mobile. Static catalog definitions and icon maps are hoisted outside components; derived preview totals are memoized and independent API requests are started in parallel where applicable.

### 8. Existing isolation and safety remain authoritative

Role skills are descriptive operating capabilities inserted into each new session's private context. They do not grant tools or permissions. Shared context remains container-scoped, private context stays session-scoped, and all cross-session content still requires explicit recipient Handoff. Presets keep approval enabled and budgets within server constants.

## Risks / Trade-offs

- [Keyword recommendation can misclassify an unusual goal] → Return three ranked options, expose reasons, allow browsing/change and use a neutral generic fallback.
- [One-click start can create unexpected cost] → Show total starter token/call/cost limits before the action, keep approvals enabled and offer create-later.
- [Catalog changes could alter historical meaning] → Require version match and persist the complete applied snapshot.
- [Partial queue outage after commit] → Return dispatch warnings, leave runs PENDING and make bulk start retryable.
- [Too many preset roles can overwhelm small projects] → Bound enabled roles to 2–8, provide conservative defaults and allow disabling optional roles.
- [Source attribution could be mistaken for bundled software] → Label LangGraph as the directly bundled graph runtime, and label CrewAI/MetaGPT/AutoGen/CAMEL/Semantic Kernel as compatible schemas or attributed patterns rather than installed executors.
- [LangGraph or YAML dependency changes affect startup] → Pin a compatible major range, validate every preset at import, and keep the previous manual container path independent of preset loading.

## Migration Plan

1. Add compatible LangGraph/PyYAML dependencies and validate the catalog during tests.
2. Add nullable provenance/snapshot/idempotency columns and the unique idempotency constraint.
3. Deploy the catalog, recommendation and instantiation APIs; existing clients continue using the unchanged manual endpoint.
4. Deploy the new frontend creation flow and API contract documentation.
5. Rollback frontend/API usage first, then remove preset endpoints/dependencies and downgrade the additive columns; existing manual containers and sessions are unaffected.

## Open Questions

None for the initial catalog. User-authored presets, remote semantic recommendation and automatic team scaling remain separate future changes.
