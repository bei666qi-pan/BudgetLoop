# Tasks: token-observatory-ui-polish

## 1. Token observatory derivation logic

- [x] 1.1 Create `web/lib/observatory.ts` with pure derivation functions over `LlmCall[]`: token totals (prompt/completion/reasoning/cache), null-aware cost sum, success rate by `request_status`, cache-hit rate, average `duration_ms`/`ttft_ms`, per-model and per-call-kind breakdowns, cumulative token and cost time series (x = `ended_at ?? started_at`, capped at latest 500 points)
- [x] 1.2 Add `web/__tests__/observatory.test.ts` covering: empty call list, mixed null fields, all-null cost (stays unavailable), cache-hit denominator, series ordering and cap; `npm test` green

## 2. Token observatory panel UI

- [x] 2.1 Create `web/components/TokenObservatory.tsx` (presentational, props `{calls, budgetDetail}`): aggregate metric tiles using the shared stat treatment, cumulative token chart and cost chart via `SvgLineChart`, per-model/per-kind breakdown via shared `ProgressBar`, per-call metering list surfacing `ttft_ms`, reasoning/cache tokens, provider, retry count, token source; unavailable values labeled, never zero-filled
- [x] 2.2 Wire an `observatory` tab into `web/app/runs/[id]/page.tsx` as the first/default tab, fed by the existing polled state (no new fetching); empty state when a run has no calls
- [x] 2.3 Add `web/__tests__/token-observatory.test.tsx` rendering the panel with fixture calls (aggregates visible, cost-unavailable label, sparse-field marking); `npm test` green

## 3. Visual system consolidation

- [x] 3.1 Palette cleanup: tokenize off-palette colors in `SvgLineChart.tsx`, `BudgetView.tsx` (teal, raw `red-*`), run-page approval banner gradient, and `bg-[#...]` one-offs in container pages; chart colors sourced from one constants module
- [x] 3.2 Canonical primitives: move the run-page underline tabs into `ui.tsx` as `Tabs` and migrate the run page; migrate `LlmCallsTable` and `BudgetView` tables onto `.data-table`; replace inline progress bars in `runs/[id]/page.tsx`, `report/page.tsx` (`ResourceRow`), and `SessionInspector.tsx` with shared `ProgressBar`; collapse duplicate status-style maps in `LlmCallsTable.tsx` onto `statusClass()`/`STATUS_LABELS`
- [x] 3.3 Fix undefined classes: replace `page-title`/`page-description` with `page-heading`/`page-subtitle` in `web/app/settings/ai/page.tsx`; replace `accent-blue-600` checkbox utilities with the accent token
- [x] 3.4 Delete dead code after repo-wide import checks: `web/components/RunStatusBar.tsx`, `StatusBadge.tsx`, `ApiHealthBanner.tsx`, and unused `ui.tsx` exports (`Card`, `Spinner`, `ErrorBar`/`ErrorBanner`, `StatCard`, old `TabBar`); fix the stale "Modern Dark Theme" comment in `ui.tsx`
- [x] 3.5 Rewrite `design-system/budgetloop/MASTER.md` to document the shipped light-blue theme (palette, surfaces, radii, shadows, typography, primitives) and remove dark-theme claims
- [x] 3.6 Visual consistency pass across routes (dashboard, new, runs, report, containers, settings): uniform spacing/section titles/cards per the shared classes; `npm test` and `npm run build` green

## 4. Verification and preview

- [x] 4.1 `cd web && npm test` exits 0 with new and existing tests
- [x] 4.2 `cd web && npm run build` exits 0
- [x] 4.3 Start backend via docker-compose (`postgres`, `valkey`, `new-api`, `control-plane`, seeded demo run) and `next dev` for the frontend; confirmed via headless-browser screenshots that the run detail page renders the observatory panel with real API data (fixed a real llm-calls response-unwrapping bug in `runs/[id]/page.tsx` found during this preview)
