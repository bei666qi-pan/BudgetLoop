# Verification

## Automated checks

- Backend focused runtime/workspace tests: 57 passed; final managed-runtime tests: 10 passed.
- Backend full suite: 560 passed, 55 skipped. Skips are the existing PostgreSQL/Docker integration cases unavailable in this local test environment.
- Ruff: passed for the changed runtime and test files.
- Mypy: passed for the managed capability and runtime proxy modules.
- Frontend: 7 files and 143 tests passed.
- Next.js production build: passed; `/settings/ai` prerendered successfully.
- `docker compose config --quiet`: passed. It emitted expected warnings for unset deployment secrets in the local shell.
- Product-source scan found no Sangfor URL, DeepSeek deployment ID, deployment label or aTrust value outside this change record and user-local application support.
- `openspec validate connect-sangfor-deepseek-runtime --strict`: passed.

## Local preview and security checks

- Started the local frontend on `127.0.0.1:3000` and backend on `127.0.0.1:8000`.
- Saved the operator's compatible gateway profile through `/settings/ai`; refresh retained all non-secret fields.
- The password field was never prefilled and the public page/API exposed only `secret_configured`.
- Toggled managed-app inheritance off, saved and verified the disabled disclosure; toggled it back on and left the final state enabled.
- Confirmed title, nonblank DOM, zero horizontal overflow at the available 1280px viewport, no console warnings/errors and no framework error overlay.
- Only the bounded `/v1/models` preflight was attempted. No model generation or paid request was made.
- aTrust client processes and connected UI were present, but the gateway preflight timed out. The UI reports the redacted actionable aTrust timeout; no MFA, TLS or policy bypass was attempted.
- The local preview processes were stopped after browser verification.

## Frontend design review — Mode 1

Verdict: Pass. No blocking or major findings; no corrective redesign was warranted.

- User path/action hierarchy: one primary save-and-check action; configuration, runtime policy and status are grouped in reading order.
- Design-system/token use: existing `surface`, `input-base`, `btn`, semantic color and responsive grid tokens are reused; the established light-blue direction is preserved.
- Accessibility: native labels, password semantics, checkbox/select controls, disabled states, `role=alert`, `role=status`, visible focus styles from the shared components and text labels in addition to color.
- Responsive behavior: the two-column layout collapses through existing `sm`/`xl` breakpoints and inputs use minmax/full-width constraints. The in-app Browser was fixed at 1280×720, so narrow-screen behavior was verified from responsive code and automated tests rather than a mobile screenshot.
- Trustworthy behavior: network errors identify the configured access route and next action; the page explains hidden reasoning, write-only secrets, server-side inheritance, short-lived scoped credentials and browser/server boundaries.

## Visual fidelity to the accepted BudgetLoop concept

- Preserves the white canvas, restrained pale-blue ambient background and blue accent hierarchy.
- Reuses the same compact top navigation, active underline and right-side connection chip.
- Matches the concept's rounded white surfaces, fine borders and low-elevation shadows.
- Maintains the wide primary workspace plus narrower sticky summary rail.
- Keeps dense operational content readable through consistent field spacing, compact labels and monospace model/endpoint values.
- Uses green for security confirmation and amber for degraded connectivity, matching semantic status treatment without changing the core palette.

Final browser capture: `/Users/qi/.codex/visualizations/2026/07/25/019f9771-ddc3-7a83-b321-43604781a6b0/budgetloop-ai-settings-final.png`.
