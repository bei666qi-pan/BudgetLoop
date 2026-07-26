# Verification record

Date: 2026-07-26

## Outcome

The conversational home entry is implemented and runnable. A plain-language goal produces one
server-validated, editable Agent Team review card; the operator-controlled folder policy remains
separate; only the final idempotent confirmation can create or dispatch work.

Verification uses three evidence classes:

- **Automated**: full backend/frontend suites and production build.
- **Browser**: production Docker UI exercised at desktop and 390 CSS px.
- **Native**: the rebuilt macOS app, `NSOpenPanel`, WebKit bridge and permission-state handoff.

No final native “确认并启动” click was made during manual verification because that action would
create five real Agent sessions and could consume an externally billed model budget. The same
commit-boundary request, isolation defaults, atomic transaction, idempotency, full-access validation,
worktree uniqueness, mount/Git failures and metering presentation are covered by the passing automated
suite. This distinction is intentional and is not represented as a live Agent execution.

## Commands and results

- `cd backend && .venv/bin/pytest tests/ -q`
  - 657 passed; 2 non-failing warnings; 88.45% coverage.
- `cd web && npm test -- --run`
  - 10 files, 169 tests passed.
- `cd web && npm run build`
  - production build passed; `/` first-load JS 121 kB in the local build.
- `./desktop/build.sh`
  - Swift app compiled, ad-hoc signature validated, root app and local zip rebuilt.
- Docker production smoke:
  - `GET /api/health` returned `{"status":"ok"}`.
  - `POST /api/task-drafts` completed in the UI with a truthful `local_fallback` result.
  - control-plane, worker and web were running during Browser/native checks.

## Browser and native evidence

- Desktop empty, planning, ready-isolated, ready-full-access, error and recent-work states were
  inspected in the in-app Browser.
- At 390 px, `documentElement.clientWidth === scrollWidth === 390`; folder mode, path, acknowledgement
  and the final action remained in document order with no horizontal page overflow.
- Desktop and mobile captures are stored in `evidence/home-ready-desktop.png` and
  `evidence/home-full-access-mobile-390.png`.
- Browser console contained no application errors or warnings.
- Production focus recheck after the Design Review correction:
  - active element: `SECTION`;
  - `tabindex=-1`;
  - `aria-labelledby=setup-review-heading`;
  - resolved label: “确认这份配置，就可以开始”;
  - polite live text: “建议配置已就绪”.
- Native app check:
  - rebuilt `BudgetLoop.app` adopted the healthy local stack;
  - toolbar “选择项目文件夹” opened a real macOS `NSOpenPanel`;
  - selecting `/Users/qi/budgetloop-e2e` and then creating a draft set “直接修改项目”, populated the
    exact path, left the acknowledgement unchecked and kept “确认并启动” disabled;
  - the task list remained at two entries before and after preview, corroborating the no-side-effect
    draft contract.

## Mode 1 frontend design review

Scope was limited to action hierarchy, design-system/token use, accessibility, responsive behavior
and trustworthy feedback.

| Pillar | Result | Evidence |
|---|---|---|
| Frictionless | Pass | Core isolated flow is description → generate → confirm; advanced editing and permissions use progressive disclosure. |
| Quality Craft | Pass after correction | Existing Tailwind tokens/primitives are reused; keyboard, reduced-motion and 390 px checks pass. |
| Trustworthy | Pass | AI/local provenance, no-side-effect preview, hard budgets, approval and folder authorization are explicitly separated. |

One production-only accessibility timing defect was found: `setTimeout(0)` attempted to focus an
unnamed wrapper before React mounted it, leaving focus on `body`. The review region now owns the ref
and accessible name, and a state effect focuses it only when planning reaches `ready` or
`needs_input`. Targeted tests (21/21), build and real Browser focus inspection passed after the fix.

## Scenario evidence map

Every scenario is listed below. “Automated” refers to the full passing suites above.

| Capability / requirement | Scenarios | Evidence |
|---|---|---|
| conversational-task-entry / Plain-language home intake | First-time operator describes an outcome; Returning operator starts new work | Browser empty/returning states; `web/__tests__/home-task-intake.test.tsx`. |
| conversational-task-entry / Bounded and validated setup draft | AI returns a valid known setup; AI invents configuration; Input exceeds a bound | `backend/tests/test_task_drafts.py` covers valid, unknown-key/preset, malformed, oversized and request-bound cases. |
| conversational-task-entry / Explainable graceful fallback | AI draft succeeds; AI draft is unavailable | Backend AI/fallback tests plus Browser `local_fallback` provenance card. |
| conversational-task-entry / Safe follow-up refinement | Operator adds a constraint; Prompt requests elevated access | Backend previous-draft bounds; frontend edit/refinement and prompt-path isolation tests. |
| conversational-task-entry / Confirmation is the only commit boundary | Operator previews a draft; Operator confirms a valid draft; Confirmation response is lost | Zero-persistence/dispatch backend assertions; atomic preset creation and retained idempotency-key retry tests. |
| conversational-task-entry / Recoverable intake states | Newer request replaces planning; Draft request fails | Vitest stale-response suppression, planning/error/retry and retained-input coverage. |
| operator-workspace / Conversational home hierarchy | Home page has no tasks; Home page has existing tasks; Operator prefers advanced setup | Browser states and accessible advanced links; home-page Vitest. |
| operator-workspace / Attention-preserving home state | Existing run needs attention | Vitest keeps waiting-approval task, direct action, search and filters usable with a ready draft. |
| isolated-session-workspaces / Explicit selected-folder authorization | Prompt mentions a local path; Native folder picker is used | Prompt-path Vitest plus native `NSOpenPanel`/WebKit bridge check with `/Users/qi/budgetloop-e2e`. |
| isolated-session-workspaces / Full-access team worktree isolation | Full-access sessions provision successfully; Worktree cannot be honored | Real temporary Git worktree test in `test_cli_engine_client.py`; API/workspace/orchestrator uniqueness and fail-closed tests. |
| isolated-session-workspaces / One folder policy and one enforcer | Worker receives persisted full access; Persisted policy is invalid | `test_workspace_manager.py`, `test_orchestrator_full.py` and shared workspace-policy tests. |
| frontend-experience-system / Accessible conversational intake | Keyboard-only operator creates a draft; Planning state changes | Vitest keyboard/live/focus checks; real Browser named-region focus recheck. |
| frontend-experience-system / Responsive setup review | Draft is reviewed on a narrow viewport | Browser 390 px DOM and visual inspection; no overflow. |
| frontend-experience-system / Trustworthy AI and authorization presentation | Local fallback is used; Writable access is not confirmed; Confirmation fails | Browser fallback/full-access states and Vitest retained-draft/retry/error assertions. |
| agent-team-presets / Catalog-constrained conversational team draft | Draft selects a trusted preset; Selected preset changes before confirmation | Draft parser/catalog tests and catalog-derived role/budget helpers; advanced preset route remains linked. |
| agent-team-presets / Folder-aware preset instantiation | Isolated team is created; Full-access team is created; Full access is incomplete or unsafe; Existing client omits new fields | `backend/tests/test_work_containers_api.py` transaction, path/ack/worktree, rollback and compatibility cases. |
| agent-team-presets / Draft and creation provenance | AI recommendation is confirmed | Preset snapshot assertions store public source/effective policy without prompt or credential fields. |
| guided-task-creation / Draft-backed configuration review | Ready draft is reviewed; Operator edits a suggested field; Advanced configuration is requested | Browser review card and Vitest goal/criteria/roles/budget progressive-disclosure checks. |
| guided-task-creation / Permission-aware final confirmation | Isolation is retained; Writable access is selected; Writable selection changes | Browser isolated/full-access checks; Vitest path/ack reset; native picker kept final action disabled until renewed acknowledgement. |

## Open-source lineage

- **OpenAI Codex** (`openai/codex`, Apache-2.0; pinned under `vendor/agent-engines/codex`):
  - permission vocabulary from `codex-rs/protocol/src/config_types.rs` (`SandboxMode`);
  - declarative writable-root policy from `codex-rs/protocol/src/permissions.rs`;
  - policy/enforcer translation from `codex-rs/sandboxing/src/manager.rs`;
  - explicit approval presentation from `codex-rs/tui/src/bottom_pane/approval_overlay.rs`.
- **OpenHands** (`OpenHands/OpenHands`, MIT core; pinned under `vendor/agent-engines/openhands`):
  - composer/start separation follows
    `frontend/src/components/features/chat/components/chat-input-container.tsx` and
    `frontend/src/hooks/mutation/use-unified-start-conversation.ts`;
  - BudgetLoop continues to reuse the existing agent-server execution path rather than implementing a
    new agent loop.
- Trusted team topology continues the already archived LangGraph/CrewAI/MetaGPT-derived preset work
  documented in `openspec/changes/archive/2026-07-25-add-smart-agent-team-presets/research.md`; those
  projects supply bounded patterns, not permission or runtime authority.

