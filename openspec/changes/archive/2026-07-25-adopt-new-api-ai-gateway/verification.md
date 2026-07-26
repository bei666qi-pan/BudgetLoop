# Verification record

Date: 2026-07-25

## Supply chain and infrastructure

- `QuantumNous/new-api` was reviewed at 43,370 GitHub stars on 2026-07-25,
  pinned to release `v1.0.0-rc.21` and revision
  `bde9b2f44887d34ec54799ae191d50f97914359e`.
- The source, AGPL-3.0 boundary and provenance are recorded under
  `vendor/ai-gateways`; BudgetLoop consumes New API as a separately deployed
  HTTP service and does not link its source into the MIT-licensed process.
- `docker compose config --quiet`: passed. The local Docker daemon was not
  available, so this verification does not claim a live New API container run.
- Browser AI-ready behavior used a local fixed-response HTTP mock. No real or
  paid model request was made.

## Backend

- `.venv/bin/pytest -q`: 550 passed, 55 skipped, 80.37% coverage.
- The 55 skipped cases are PostgreSQL integration cases whose testcontainers
  could not start because the local Docker daemon is unavailable; the skips are
  environmental rather than assertion failures.
- Focused gateway and recommendation suite: 43 passed.
- Core and configuration regression suite: 62 passed.
- Worker orchestrator regression suite: 100 passed.
- Scoped Ruff checks for the gateway, recommendation boundary and tests: passed.
- Scoped Mypy checks for the gateway and recommendation boundary: passed.

## Frontend

- `npm test -- --run`: 6 files and 140 tests passed.
- `npm run build`: production build passed; `/containers/new` first-load JS is
  121 kB.

## Browser interaction verification

- Verified the complete desktop flow at 1280 px:
  `/containers/new` → puzzle-game goal → AI-ranked game team → controlled 503
  → deterministic local recommendation.
- Healthy status displayed `AI 智能推荐已就绪 · New API`, exposed only the
  configured safe console URL, and opened it with `_blank` plus
  `noopener noreferrer`.
- Successful mock AI output displayed `AI 已完成推荐 · 本地目录已校验`, selected
  the trusted game-development preset and kept all team details catalog-owned.
- A controlled upstream 503 displayed `已自动切换到本地推荐` and
  `上游模型暂不可用；团队创建功能不受影响`; no blocking creation error was
  introduced and both creation actions remained enabled.
- The page had no desktop horizontal overflow
  (`scrollWidth === clientWidth === 1280`), no application console errors or
  warnings, and no framework error overlay.
- The in-app Browser runtime ignored requested 390 × 844 viewports, disallowed
  window resizing and rejected an isolated data-URL iframe. A fresh 390 px
  screenshot could therefore not be produced in this pass. The changed UI uses
  the existing responsive Tailwind breakpoints, `flex-wrap` and `min-w-0`, and
  preserves the previously verified 390 px page structure; this remains the
  only manual device-level follow-up.

## Mode 1 design review

- `frontend-design-review` was run only after the UI was complete and runnable,
  in Mode 1: Design Review.
- The ARIA live status initially contained an interactive console link. The
  `role="status"` boundary was narrowed to the status text only.
- The external administration link initially used only `noreferrer`; it now
  uses `noopener noreferrer`.
- Frontend tests, production build and the affected Browser interaction were
  rechecked after both corrections.

## Visual fidelity ledger

- The persistent navigation and H1 hierarchy are unchanged.
- The primary form and right-side team-preview proportions are unchanged.
- The white surfaces, pale-blue borders and deep-blue primary actions continue
  to use the existing design-system tokens.
- Gateway state is an inline status treatment, not a new competing card or page
  hierarchy.
- AI-ready, AI-result and fallback messages reuse the existing accent, success
  and warning semantics.
- Existing radius, shadow and spacing rhythms are preserved.
- The primary “create and start” action remains dominant; “create for later”
  remains secondary.
- Recommendation provenance is explicit without exposing credentials, hidden
  context or model reasoning.

## Routing decision

- BudgetLoop does not add a second LLM call to choose an LLM. New API owns model
  mapping, channel priority, weighted selection, retry and rate limiting.
- This avoids extra latency, cost, prompt exposure and nondeterministic routing;
  LiteLLM remains available only through the explicit `legacy-litellm` profile.
