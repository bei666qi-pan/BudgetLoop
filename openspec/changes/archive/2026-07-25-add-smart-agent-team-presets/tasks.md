## 1. Catalog and Recommendation Domain

- [x] 1.1 Add pinned-compatible LangGraph/PyYAML dependencies and a typed CrewAI-compatible YAML loader for the generic, software, game, business, launch, content, research, data and support catalog.
- [x] 1.2 Implement category filtering, stable serialization, version lookup, aggregate starter budgets and MetaGPT-style SOP validation.
- [x] 1.3 Compile recommendation and activation workflows with LangGraph, including preference weights, ranked reasons, public match signals, activation waves and a conditional generic fallback.
- [x] 1.4 Add focused catalog/graph tests covering every preset, source provenance, CrewAI fields, ranking, fallback, determinism, topology compilation and invalid YAML/stages.

## 2. Persistence and Migration

- [x] 2.1 Add nullable preset id/version/snapshot and idempotency fields to `WorkContainer` with an additive uniqueness constraint.
- [x] 2.2 Add a reversible Alembic migration and model tests for provenance defaults, applied snapshots and duplicate creation keys.

## 3. Preset and Team Creation API

- [x] 3.1 Add typed list and recommend endpoints with authentication, category/preference validation and no external recommendation dependency.
- [x] 3.2 Refactor session record creation into a reusable transaction-scoped helper without changing the existing single-session endpoint.
- [x] 3.3 Add idempotent preset instantiation with bounded role overrides, atomic container/session/task/run/budget/phase persistence and post-commit dispatch reporting.
- [x] 3.4 Add retry-safe bulk team start that dispatches only owned PENDING runs and returns accepted, skipped and warning facts.
- [x] 3.5 Extend container serialization and API contract documentation with optional provenance, applied snapshot and additive endpoint schemas.
- [x] 3.6 Add PostgreSQL/API tests for auth, catalog, recommendation, atomic rollback, idempotency, overrides, start-now, start-later, dispatch failure and legacy endpoint compatibility.

## 4. Replaceable Execution Engines

- [x] 4.1 Add a revision-pinned manifest and safe bootstrap for shallow OpenHands core, Codex, Gemini CLI and OpenCode source checkouts, with license and maintenance provenance.
- [x] 4.2 Add typed engine registry/capability models, availability preflight and an authenticated engine catalog endpoint with OpenHands as the compatibility default.
- [x] 4.3 Add a BudgetLoop-owned adapter protocol and CLI/server adapters that normalize engine lifecycle and public events without delegating control-plane authority.
- [x] 4.4 Persist additive default/per-role engine selection in preset snapshots and Run model configuration, validate unavailable engines truthfully and preserve legacy defaults.
- [x] 4.5 Add focused registry, manifest, adapter command, unavailable-engine and legacy-default tests.

## 5. Beginner-first Frontend

- [x] 5.1 Add TypeScript contracts, icon/category/engine maps and pure helpers for recommendations, overrides, aggregate budgets and derived project names.
- [x] 5.2 Build reusable goal recommender, preset browser, role list, source attribution and team preview/action components from the selected concepts.
- [x] 5.3 Replace `/containers/new` with Smart Recommendation and Browse Presets modes, debounced recommendation, transparent reasons and progressive advanced settings.
- [x] 5.4 Implement role enable/edit/engine controls, start-now/create-later submissions, idempotency, trustworthy busy/error feedback and navigation to the created team.
- [x] 5.5 Add preset/engine provenance and explicit start-team action to the container workspace for staged teams.
- [x] 5.6 Implement the mobile layout with overflow-safe category/role content and a reachable budget/action region.
- [x] 5.7 Add frontend tests for recommendation state, browsing, totals, role bounds, engine choice, source links, both creation actions and staged-team start.

## 6. Verification and Delivery

- [x] 6.1 Run backend Mypy, focused Ruff and full pytest; correct regressions and record Docker/PostgreSQL environment skips separately.
- [x] 6.2 Run frontend Vitest and a clean production build with no concurrent dev/build cache mutation.
- [x] 6.3 Run the app with Browser/IAB and verify smart recommendation, preset browsing, engine choice, role edits, start-now/create-later, desktop/mobile overflow and console health.
- [x] 6.4 Compare both concept references and final captures with `view_image`, complete a five-plus-point fidelity ledger and run the above-the-fold copy diff.
- [x] 6.5 Load `frontend-design-review` in Mode 1, apply only verified targeted findings and recheck the corrected UI.
- [x] 6.6 Strictly validate OpenSpec, sync delta specs and archive the completed change.
