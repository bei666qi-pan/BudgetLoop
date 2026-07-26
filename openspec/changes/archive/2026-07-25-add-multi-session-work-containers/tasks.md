## 1. Persistence and Domain Model

- [x] 1.1 Add `WorkContainer`, `WorkSession`, and `SessionMessage` models with lifecycle, ownership, delivery, idempotency, run-linkage, and optional worktree fields.
- [x] 1.2 Add an Alembic migration with foreign keys, uniqueness constraints, bounded indexes, and a reversible downgrade for the collaboration tables.
- [x] 1.3 Add focused model and migration tests covering defaults, constraints, cascading behavior, and legacy task/run compatibility.

## 2. Work Container and Session API

- [x] 2.1 Add typed request/response schemas and serialization helpers for container summaries, container detail, sessions, messages, and optional run ownership.
- [x] 2.2 Implement authenticated create/list/get/update work-container endpoints with lifecycle and workspace-policy validation.
- [x] 2.3 Implement atomic session creation that creates the normal task, run, budget, phases, and queue dispatch while preserving idempotency.
- [x] 2.4 Implement nested session detail and pause endpoints with 404 ownership semantics and safe lifecycle transitions.
- [x] 2.5 Implement recipient-specific message and handoff creation with sender validation, content bounds, delivery state, and idempotency keys.
- [x] 2.6 Register the router and document the additive work-container API plus optional ownership fields on legacy run payloads.
- [x] 2.7 Add API tests for authentication, nested ownership, idempotency, atomic creation, pause behavior, pagination bounds, and existing task/run routes.

## 3. Controlled Session Collaboration

- [x] 3.1 Add a collaboration service that queries only queued messages for the owning recipient session and formats a compact immutable-ID-labelled inbox.
- [x] 3.2 Integrate inbox delivery at the orchestrator iteration boundary and mark messages delivered only after the OpenHands send succeeds.
- [x] 3.3 Emit auditable collaboration delivery events and expose public agent-output transcript entries without exposing private context or hidden reasoning.
- [x] 3.4 Add worker tests for recipient isolation, deterministic formatting, successful delivery, failed-send retry behavior, and duplicate submission handling.

## 4. Optional Isolated Worktrees

- [x] 4.1 Extend workspace provisioning with server-generated, sanitized session branch names and `.budgetloop/worktrees/<session-id>` paths inside the Docker workspace.
- [x] 4.2 Persist worktree branch/path/runtime status, pass the selected working directory to OpenHands, and fail closed with an actionable workspace error when setup is invalid.
- [x] 4.3 Add tests for enabled and disabled policies, non-Git repositories, command/path safety, and workspace failure reporting.

## 5. Product and Visual Design

- [x] 5.1 Inventory the existing light-blue design tokens, shell, responsive patterns, and reusable controls before extending the interface.
- [x] 5.2 Generate and compare ImageGen concepts for the Agent Team overview and the three-region collaboration workspace, then store the selected references with a fidelity ledger.

## 6. Agent Team Frontend

- [x] 6.1 Add typed client contracts and presentation helpers for containers, sessions, transcripts, handoffs, derived team state, and worktree/runtime facts.
- [x] 6.2 Add the `/containers` overview and `/containers/new` creation flow with clear project hierarchy, policy choices, validation, and trustworthy empty/error/loading states.
- [x] 6.3 Add the `/containers/[id]` responsive collaboration workspace with project summary, session rail, selected conversation, shared context, inbox, and runtime/worktree facts.
- [x] 6.4 Add accessible create-session, switch-session, pause, message, and handoff interactions with preserved per-session budgets and explicit delivery feedback.
- [x] 6.5 Extend shared navigation and optional run ownership links without regressing `/`, `/new`, `/runs/[id]`, or `/runs/[id]/report`.
- [x] 6.6 Add frontend unit tests for presentation logic, forms, routing states, accessibility-critical controls, polling cleanup, and collaboration interactions.

## 7. Verification and Delivery

- [x] 7.1 Run backend formatting/static checks and pytest; correct failures and record any environment-limited verification.
- [x] 7.2 Run frontend Vitest and production build; correct failures and verify legacy routes remain compatible.
- [x] 7.3 Run the application and use the in-app browser to verify desktop/mobile layouts, key user paths, console health, and concept-to-render fidelity.
- [x] 7.4 Run `frontend-design-review` in Mode 1 on the completed runnable UI, apply verified targeted corrections, and recheck the result.
- [x] 7.5 Strictly validate OpenSpec, sync delta specs, and archive the completed change after all tasks pass.
