# Design: token-observatory-ui-polish

## Context

The run detail page (`web/app/runs/[id]/page.tsx`) already polls `GET /api/runs/{id}`, `/llm-calls`, `/budget`, and `/events` every 3s and holds `calls: LlmCall[]`, `budgetDetail`, and `events` in state. The `LlmCall` type (`web/lib/types.ts:144-175`) carries far more metering than the UI shows: `ttft_ms`, `reasoning_tokens`, `cache_read_tokens`, `cache_write_tokens`, `token_source`, `provider`, `retry_count`, `request_status`, `effective`. Today this data appears only as rows in `LlmCallsTable`, with no aggregates or trends.

Separately, the frontend's visual system has drifted: `design-system/budgetloop/MASTER.md` documents a dark OLED theme while the app ships a light-blue theme (`tailwind.config.ts`); `RunStatusBar.tsx`, `StatusBadge.tsx`, `ApiHealthBanner.tsx` are dead code; tables, tabs, progress bars, and status badges each exist in 2–3 competing implementations; several files use off-palette hex values.

Constraints: frontend-only change; no new backend endpoints (per-iteration series endpoints do not exist — series must be derived client-side); PostgreSQL remains the sole business source of truth; verification is `npm test` + `npm run build`.

## Goals / Non-Goals

**Goals:**
- A "观测" (observatory) panel on the run detail page that turns raw llm-call rows into metering insight: aggregates, trends, per-call richness.
- One canonical visual system: shared table/tab/progress/badge primitives, palette-only colors, design doc matching the shipped theme.
- Unit tests for all new derivation logic; component test for the panel.

**Non-Goals:**
- Backend or worker changes, new API endpoints, SSE migration, dark-mode re-theme, run-execution behavior changes.
- A general-purpose charting library — we extend the existing dependency-free SVG components only as needed.

## Decisions

### D1: Panel is a new first tab fed by existing state, no new fetching
The observatory becomes a `observatory` tab in the run page's existing tablist, rendered by a new presentational component `web/components/TokenObservatory.tsx` receiving `{calls, budgetDetail, events}`. It is placed first and becomes the default tab: token metering is the product's headline feature, and the current-activity/budget-health blocks above the tabs already cover live status (preserving the run-command-center state hierarchy). Alternative considered: a separate `/runs/[id]/observatory` route — rejected because it duplicates the page's polling orchestration for zero benefit.

### D2: All metrics derived by pure functions in `web/lib/observatory.ts`
A single pure module computes, from `LlmCall[]`: total/prompt/completion/reasoning/cache tokens, estimated cost sum (null-aware — cost stays "unavailable" when every `estimated_cost` is null, per the no-fabricated-zeroes rule), success rate (`request_status`), cache-hit rate (`cache_read_tokens / (prompt_tokens + cache_read_tokens)` over calls that report both), average `duration_ms` and `ttft_ms`, per-model and per-call-kind breakdowns, and two time series (cumulative tokens, cumulative cost, x = `ended_at ?? started_at`). Pure functions keep the component thin and give Vitest full coverage without rendering. Derivation is memoized in the component (`useMemo`) and series are capped (latest 500 points) so the 3s poll loop stays cheap on long runs.

### D3: Reuse `SvgLineChart`; add one small `SvgBarChart` primitive
Cumulative token and cost trends render as two `SvgLineChart`s. Per-model token distribution renders as horizontal bars via the existing `ProgressBar`, not a new chart type. A minimal dependency-free `SvgBarChart` is added only if per-call token bars are needed for readability; both charts take colors from the palette (D5). No chart library dependency is introduced.

### D4: Consolidate on the shipped patterns; delete the dead ones
- **Tabs**: the run page's inline underline-tab style becomes the canonical `Tabs` primitive in `ui.tsx`; the unused `TabBar` is removed. Run page migrates to `Tabs`.
- **Tables**: `.data-table` (globals.css) is the single table system; `LlmCallsTable` and `BudgetView` phase tables migrate onto it.
- **Progress bars**: `ProgressBar` from `ui.tsx` replaces inline bars in `runs/[id]/page.tsx`, `report/page.tsx` (`ResourceRow`), and `SessionInspector.tsx`.
- **Badges**: `statusClass()` + `STATUS_LABELS` in `lib/presentation.ts` stays the single source; duplicate maps in `LlmCallsTable.tsx` are removed; dead `StatusBadge.tsx` is deleted.
- **Dead code**: `RunStatusBar.tsx`, `StatusBadge.tsx`, `ApiHealthBanner.tsx` and unused `ui.tsx` exports (`Card`, `Spinner`, `ErrorBanner`, `StatCard`) are deleted after a repo-wide import check; `AppShell` keeps its own health banner (it is the live one).
- **Settings page**: undefined `page-title`/`page-description` classes are replaced with the defined `page-heading`/`page-subtitle`.

### D5: Palette tokens replace off-palette hex values
`SvgLineChart` (`#2563eb`, `#ef4444`, slate grid/label colors), `BudgetView` (teal `#0d9488`, raw `red-*` utilities), the run page approval banner gradient, and one-off `bg-[#...]` values in container pages are moved onto the tailwind palette (`accent`, `success`, `warning`, `critical`, `muted` tokens). Chart colors are passed as props/typed constants from one module so SVG `stroke`/`fill` attributes stay in sync with the palette.

### D6: Design-system doc follows the shipped implementation
`design-system/budgetloop/MASTER.md` is rewritten to describe the light-blue theme that actually ships (background `#F7FAFF`, foreground `#0B1F44`, accent `#1769F6`, semantic success/warning/info/critical, existing radii/shadows/typography). Rationale: the implementation is what users see and what the hackathon demo depends on; re-theming the app dark is a larger, riskier change with no user demand. The stale "Modern Dark Theme" comment in `ui.tsx` is corrected in the same pass.

## Risks / Trade-offs

- [Deleting dead components breaks a missed import] → repo-wide `grep` for each symbol before deletion, then `npm run build` + `npm test` must exit 0.
- [3s re-derivation on long runs costs CPU] → pure derivation + `useMemo` + 500-point series cap; derivation is O(n) over calls.
- [Cost data is null when prices are unconfigured] → aggregates and charts label values as 不可用/"价格未配置" instead of plotting zeroes, matching the run-command-center partial-data rule.
- [Consolidating table/tab styles shifts visuals on untouched pages] → migration keeps the currently-shipped visual treatment of each page; only the implementation mechanism changes, so the visible diff stays minimal.
- [New default tab changes the first thing operators see] → accepted deliberately; the blocks above the tabs retain live status, and the change is recorded in the `run-command-center`-adjacent UX without altering its requirements.

## Migration Plan

Purely frontend. Land in two verifiable steps: (1) observatory panel + derivation tests, (2) visual consolidation + doc rewrite. Each step must leave `npm test` and `npm run build` green. Rollback is a git revert of the web/ and design-system/ changes; no data or API migration exists.

## Open Questions

None blocking. If full-stack preview reveals the backend cannot seed demo runs without the worker (Docker-dependent), the preview still validates the panel against real API responses for existing/seeded data, and any gap is reported rather than mocked into the UI.
