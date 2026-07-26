## Context

The frontend is a Next.js 15 App Router application with four primary product surfaces: task dashboard, task creation, run monitoring, and final report. It already consumes the required backend APIs and exposes the core data, but each route independently composes dense card-based layouts, the page shell provides little orientation, small typography carries important meaning, and mobile layouts are mostly incidental. The redesign must improve the operator journey without changing the backend contract, budget semantics, approval security boundary, or PostgreSQL ownership.

Primary stakeholders are engineers operating BudgetLoop, evaluators demonstrating budget-aware behavior, and maintainers who need a coherent component system. The design must work when the API is unavailable, data is partial, a run is active, approval is required, or the run terminates without full success.

## Goals / Non-Goals

**Goals:**

- Create one recognizable application shell and a clear lifecycle from task discovery through outcome review.
- Make the current status, next useful action, budget health, safety state, and acceptance outcome legible before secondary diagnostics.
- Preserve the depth of timeline, LLM call, budget, diff, and report data through progressive disclosure rather than removal.
- Establish reusable tokens and components for navigation, buttons, fields, status, page sections, feedback, and responsive layouts.
- Keep all existing API calls and domain types compatible while strengthening local validation, loading/error handling, and authenticated export behavior.
- Verify visual fidelity against generated full-screen concepts and verify workflows at desktop and mobile breakpoints.

**Non-Goals:**

- No backend endpoint, database, worker, orchestration, LiteLLM, OpenHands, or deployment changes.
- No new authentication model and no movement of provider credentials into browser code.
- No change to budget enforcement, pressure calculations, approval authorization, or run state transitions.
- No speculative analytics, fabricated metrics, or server state derived only from client persistence.

## Decisions

### 1. Retain the Next.js route model and API boundary

The existing routes remain the product skeleton: `/`, `/new`, `/runs/[id]`, and `/runs/[id]/report`. Route-level client components continue to fetch from the existing API helpers; PostgreSQL-backed API responses remain the source of truth. This limits risk and makes the change deployable as a frontend replacement.

Alternative considered: introduce a new state-management/data-fetching dependency and restructure the API layer. Rejected because the current data flow is adequate, the request is experience-focused, and dependency churn would add risk without improving the contract.

### 2. Use a lifecycle-oriented application shell

A shared shell will provide brand identity, global navigation, API health visibility, responsive content width, and a consistent primary action. Page-specific content will follow the operator lifecycle: overview, configure, supervise, evaluate. Active navigation is derived from the route; mobile navigation collapses without hiding the primary task action.

Alternative considered: retain isolated pages with only new styles. Rejected because styling alone would not fix orientation, action hierarchy, or journey continuity.

### 3. Use progressive disclosure for dense controls and diagnostics

Task creation will show essential intent and a recommended budget preset first, while advanced resource limits remain directly accessible. Run monitoring will lead with state, current activity, remaining budget, and approval requirements; timeline and LLM-level diagnostics remain available in purposeful sections/tabs. The report will lead with acceptance and next actions before detailed evidence.

Alternative considered: preserve every control and metric at equal visual weight. Rejected because it forces operators to interpret implementation details before deciding what to do.

### 4. Build a code-native design system from a generated visual specification

Before implementation, generate readable concepts for the dashboard, creation flow, run command center, and report in one coherent visual direction. Extract exact design tokens, typography, container rules, status colors, controls, and icon treatment into Tailwind/CSS and reusable React primitives. All application text, data, fields, tables, and controls remain code-native; generated screenshots are specifications, not shipped UI assets.

The intended direction is a calm, high-trust light operations console: airy ice-blue and near-white surfaces, crisp neutral typography, a restrained azure-to-cornflower accent inspired by premium AI productivity tools, semantic amber/red states, open panels and rails rather than nested card grids, compact but readable diagnostic text, subtle glass/material depth, and restrained motion that explains state changes. The craft target is Apple-like clarity and spacing without copying Apple or Gemini brand marks, proprietary assets, or exact layouts.

Alternative considered: directly restyle from subjective code edits. Rejected because a complete visual specification gives the multi-route redesign a coherent target and enables explicit fidelity verification.

### 5. Treat budget and safety as semantic product primitives

Budget values will consistently communicate used, remaining, limit, and pressure state with text as well as color. Approval requests remain interruptive and explicit, destructive/reject actions remain distinct, and partial or unavailable data is labelled rather than inferred. Client validation improves input quality but never claims to replace backend enforcement.

Alternative considered: simplify budget and approval content into generic progress indicators. Rejected because it would obscure the product's core differentiator and weaken trustworthy behavior.

### 6. Use resilient route states and authenticated actions

Every route will define loading, empty, API-unavailable, partial-data, and retry behavior. Report exports will use the authenticated download helper rather than unauthenticated `window.open` URLs. Run streaming/polling behavior will retain current semantics, with visible connection state and fallback messaging where existing event helpers expose it.

Alternative considered: optimistic placeholder content for missing responses. Rejected because fabricated state is unacceptable in an operator console.

### 7. Verify structure, behavior, and appearance separately

Vitest/Testing Library will cover deterministic UI behavior and helpers; `npm run build` will validate the production bundle. Browser verification will exercise the core paths at desktop and mobile sizes. After the UI is runnable, the mandated design review will evaluate action hierarchy, design-system use, accessibility, responsive behavior, and trustworthy errors/transparency; verified findings will be corrected and rechecked.

## Risks / Trade-offs

- [Broad visual change can regress information access] → Preserve every existing domain datum in an explicit route inventory and test the primary/secondary presentation states.
- [A guided form can feel slower for expert operators] → Keep sections compact, provide sensible defaults, and allow direct navigation/editing without a server-side wizard.
- [Dark semantic colors can miss contrast targets] → Pair status colors with labels/icons, verify focus and text contrast, and test keyboard navigation.
- [Live run data can reflow excessively on small screens] → Reserve stable summary regions, use overflow-safe tables/rails, and move secondary diagnostics behind responsive tabs or disclosure.
- [Generated concepts can contain inaccurate text or data] → Treat the repository's domain language and API types as the content source of truth; concepts govern visual hierarchy and component treatment, not backend facts.
- [No backend changes limits new dashboard aggregation] → Compute only presentation-safe summaries from already-returned task/run data and never imply unavailable server analytics.

## Migration Plan

1. Add the shared shell, tokens, and primitives while preserving existing route URLs.
2. Replace each route incrementally in lifecycle order and keep API adapters compatible.
3. Add/adjust frontend tests, then run Vitest and the production build.
4. Run the app against available API or deterministic mocked responses for route and responsive verification.
5. Apply the post-implementation design review corrections and rerun checks.

Rollback is a frontend file-level revert; there is no database migration or backend contract rollback.

## Open Questions

None blocking. Exact visual measurements and breakpoint adjustments will be resolved from the generated concepts and verified browser renders while keeping these behavioral requirements fixed.
