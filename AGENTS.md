# Standing conventions

## Prefer proven open-source solutions — never reinvent the wheel

- Do NOT build from scratch what a mature open-source project already provides. Before designing any non-trivial mechanism (sandboxing, permission models, packaging, UI patterns), first look for an established open-source reference — prefer projects with 10k+ GitHub stars — and adopt or adapt their design.
- Write-permission isolation / sandboxing in this project follows OpenAI Codex's design (https://github.com/openai/codex, vendored at `vendor/agent-engines/codex`): reuse its sandbox-mode model and semantics rather than inventing new ones.
- When a design is derived from an external project, cite the source project (and file/doc if applicable) in the design document so the lineage is clear.

## Testing discipline — never cheat the gate

- **Do NOT lower the bar to pass.** Never weaken assertions, relax thresholds, add fallback/dummy implementations, skip tests, or modify test criteria just to make a failing test green. A test that fails for real is a signal; burying it is a lie.
- **Do NOT bypass coverage gates.** Never raise `--cov-fail-under` limits, comment out `pytest.mark.strict` markers, or alter CI test matrices to dodge a required check. Fix the code so it genuinely meets the standard.
- **Every code change must re-verify.** After any modification, re-run the affected tests before declaring the work done. If you touched `backend/`, run `cd backend && pytest`. If you touched `web/`, run `cd web && npm test`. If you touched both, run both. Do not mark work complete while tests are still red, pending, or unsupported by actual evidence.
- **Report what you could not run.** If a test suite requires infrastructure not available in the current environment (Docker, database, GPU), state that explicitly — what was run, what was skipped, and why.

# OpenSpec default workflow

This repository uses OpenSpec as the default workflow for meaningful changes.
The source of truth is `openspec/`; do not replace it with agent-specific plans.

- For a new feature, behavior change, refactor, API-contract change, or architectural work, begin by using the OpenSpec propose workflow. Review the generated proposal, design, specs, and tasks before changing implementation code.
- For a clearly scoped typo, documentation-only correction, or trivial mechanical change, implementation may proceed directly; still update OpenSpec if the change alters committed behavior or requirements.
- Implement approved work through the OpenSpec apply workflow, complete verification in its task list, then sync and archive the change when it is finished.
- Read active changes and existing specs before proposing overlapping work. Keep specs, tasks, and code consistent.
- Use the project's documented test commands and report any verification that could not be run.

Tool entry points are generated in project-local directories. Codex uses the
`openspec-*` skills in `.codex/skills/`; Kimi Code uses the matching skills in
`.kimi/skills/` (for example, `/skill:openspec-propose`). Other supported coding
agents receive their native skills and commands through `openspec init --tools all`.
