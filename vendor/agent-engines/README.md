# Agent engine source checkouts

Run `scripts/fetch-agent-engines.sh` to reproduce the exact shallow source revisions declared in `backend/app/execution_engines/manifest.yaml`.

The generated engine directories are intentionally ignored by the parent repository: each is its own detached shallow Git checkout, while the reviewed revision and license boundary are versioned in the manifest. OpenHands uses only the MIT core; its separately licensed `enterprise/` tree is excluded by sparse checkout.

These sources provide auditable local build inputs for replaceable execution engines. BudgetLoop remains the control plane and does not import upstream databases, budgets, approvals or conversation state as business authority.

Runtime binaries are discovered in the Worker `PATH`; source presence and runtime
availability are intentionally separate facts. CLI execution is disabled by
default. Enabling it also requires an engine-scoped HOME or
`BUDGETLOOP_<ENGINE>_ENV_*` credential. OpenCode additionally requires an outer
sandbox command (or an explicit development-only host-execution opt-in).

Each CLI run receives a persistent BudgetLoop-owned repository/worktree. The
adapter enforces a bounded process timeout, normalizes only public JSON events,
keeps reasoning out of transcripts, and never changes TaskRun, budget, approval
or Handoff state directly.
