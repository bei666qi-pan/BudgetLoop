# Proposal: token-observatory-ui-polish

## Why

Fine-grained token metering is BudgetLoop's core differentiator, yet the run detail page buries per-call LLM data in a plain table tab with no aggregate metrics, no token/cost trend visualization, and many already-returned fields (`ttft_ms`, `reasoning_tokens`, cache tokens, `provider`, `retry_count`) rendered nowhere. Meanwhile the frontend has drifted from its own design system: the committed `design-system/budgetloop/MASTER.md` specifies a dark OLED theme while the app ships a light blue one, three components are dead code duplicating live UI, and off-palette hard-coded colors, two table systems, and two tab styles erode the demo's credibility.

## What Changes

- Add a **token metering observability panel** ("观测") to the run detail page: aggregate metering metrics (total/prompt/completion tokens, cost, avg duration & TTFT, success rate, cache hit rate), per-call consumption and cumulative cost trend charts reusing `SvgLineChart`, and an enhanced call breakdown that surfaces currently unused metering fields. Data comes from the already-polled `/llm-calls`, `/budget`, and `/events` endpoints — no new API.
- **System-wide UI polish**: reconcile `design-system/budgetloop/MASTER.md` with the shipped light-blue theme (documentation follows implementation, not the reverse), tokenize off-palette hard-coded colors, consolidate the duplicated table / tab / progress-bar / badge patterns onto the shared primitives in `ui.tsx`/`globals.css`, remove dead components (`RunStatusBar.tsx`, `StatusBadge.tsx`, `ApiHealthBanner.tsx` and unused `ui.tsx` exports), and fix the undefined `page-title`/`page-description` classes on the AI settings page.
- Add Vitest coverage for the new observability panel and its derivation logic.

## Capabilities

### New Capabilities

- `token-observatory`: Run-detail token metering observability — aggregate metering metrics, consumption/cost trend visualization, and enhanced per-call breakdown fed by existing llm-calls/budget/events data.

### Modified Capabilities

- `frontend-experience-system`: Visual-token and shared-primitive requirements are revised — one canonical table/tab/progress/badge treatment, semantic color tokens only (no off-palette hex values), dead primitives removed, and the design-system document updated to describe the shipped light theme.

## Impact

- **Affected code**: `web/app/runs/[id]/page.tsx`, `web/components/*` (new `TokenObservatory` panel; updates to `BudgetView`, `LlmCallsTable`, `SvgLineChart`, `ui.tsx`; deletion of `RunStatusBar.tsx`, `StatusBadge.tsx`, `ApiHealthBanner.tsx`), `web/app/globals.css`, `web/tailwind.config.ts`, `web/app/settings/ai/page.tsx`, `web/lib/*` (new derivation helpers + tests), `design-system/budgetloop/MASTER.md`.
- **Budget impact**: none — the panel is read-only presentation of existing metering data.
- **Safety impact**: none — no provider keys or new privileges; all data already reaches the frontend today.
- **API-contract impact**: none — consumes only existing read endpoints (`GET /api/runs/{id}`, `/llm-calls`, `/budget`, `/events`); no backend changes.
- **Migration impact**: none.
- **Non-goals**: backend/worker changes, new API endpoints, SSE migration of the run page, a dark-mode re-theme of the app, and any change to run execution behavior.
