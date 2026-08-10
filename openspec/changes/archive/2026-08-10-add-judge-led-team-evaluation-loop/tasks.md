# Tasks: Add Judge-Led Team Evaluation Loop

## 1. Persistence and lifecycle

- [x] Add judge policy, round, gate and finding persistence plus migration.
- [x] Provision exactly one system-managed judge WorkSession for new teams.
- [x] Idempotently backfill active/paused historical teams and preserve terminal teams.
- [x] Track judge model calls and rework usage in the existing budget ledger.

## 2. Decision loop and collaboration

- [x] Implement ordered deterministic gates that can never be overridden by the model.
- [x] Persist structured `approve | rework | blocked` model verdicts and invalid-call evidence.
- [x] Dispatch targeted judge feedback to one or more responsible Sessions.
- [x] Require durable delivery/acknowledgement and real Agent replies.
- [x] Continue rework in new TaskRuns while carrying the cumulative Session envelope.
- [x] Pause on budget/runtime/model anomalies and support bounded operator recovery.

## 3. Public API and realtime state

- [x] Add `GET /api/work-containers/{id}/judge`.
- [x] Add idempotent `POST /api/work-containers/{id}/judge/resume`.
- [x] Reuse Session budget controls for judge budget changes.
- [x] Add judge lifecycle events to the durable team SSE outbox and replay stream.
- [x] Add public judge policy/state/verdict/round/finding/gate types.

## 4. Team observatory UI

- [x] Render the judge as a fixed system Session.
- [x] Render loading, gating, reply-waiting, model-evaluation, paused and terminal states.
- [x] Group communication by judge round with sender, recipient and delivery state.
- [x] Render deterministic gate and model summaries without hidden reasoning.
- [x] Provide recovery UI for paused/blocked/budget states.
- [x] Add component and integration coverage for judge rendering and SSE refresh.
- [x] Complete frontend-design-review Mode 1 and targeted corrections.

## 5. Real team delivery and E2E

- [x] Run a real BudgetLoop team with product, architecture, logic, UI, QA, integration and judge Sessions.
- [x] Produce the tracker only through Agent worktrees and publish primary `main` via `ff-only`.
- [x] Verify real targeted judge questions, delivery confirmation, Agent replies and non-linear rework.
- [x] Serve the tracker at `http://127.0.0.1:4173` and BudgetLoop at `http://127.0.0.1:3000`.
- [x] Pass HTTP Playwright desktop/390px CRUD, persistence, validation, keyboard, network and overflow checks.
- [x] Pass backend tests, web tests/build and OpenSpec validation.
- [x] Obtain a real model-backed final judge `approve` and verify the observatory in the in-app Browser.

## 6. OpenSpec completion

- [x] Update the as-built design and delta spec.
- [x] Sync the delta to the main spec and archive the completed change.
