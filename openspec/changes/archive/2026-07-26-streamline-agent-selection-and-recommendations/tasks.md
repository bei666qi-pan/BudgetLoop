## 1. AI-first recommendation and engine policy

- [x] 1.1 Add a bounded inference-aware recommendation timeout and backend tests proving maximum-thinking compatible requests do not use the short generic read bound.
- [x] 1.2 Add trusted task-kind classification plus Codex/OpenHands recommended-engine fields to task drafts, preserving OpenHands for legacy callers.
- [x] 1.3 Add backend tests for coding/general defaults, AI and local parity, unavailable-engine truthfulness, and sanitized fallback provenance.
- [x] 1.4 Rebuild the control plane and verify a real Sangfor DeepSeek V4 Pro maximum-effort draft completes with `source=ai` without exposing credentials.

## 2. Conversational UI and interaction

- [x] 2.1 Add a concise OpenHands/Codex/Gemini CLI selector that applies an explicit choice across enabled roles and survives follow-up refinement.
- [x] 2.2 Simplify the ready review hierarchy and replace the prominent fallback panel with compact provenance plus optional details.
- [x] 2.3 Add a reusable vector BudgetLoop activity mark for planning/creation with orbit/morph motion, assistive status text, and reduced-motion behavior.
- [x] 2.4 Make Enter submit exactly once, Shift+Enter create a newline, and IME/empty/busy Enter safe; add focused interaction tests.

## 3. Task history deletion

- [x] 3.1 Implement transactional deletion of terminal standalone tasks with active/team ownership guards and complete current run-owned dependency cleanup.
- [x] 3.2 Add backend tests for success, missing task, active conflict, team-owned conflict, and rollback-preserving behavior.
- [x] 3.3 Add a secondary recent-task delete action, named confirmation, pending/error feedback, successful row removal, and frontend tests.

## 4. Verification and finish

- [x] 4.1 Run focused backend and frontend tests, Ruff, the full frontend suite, and the production Next.js build.
- [x] 4.2 Run the updated app in the browser and verify desktop/mobile primary paths, engine selection, deletion, loading motion/reduced motion, and keyboard submission.
- [x] 4.3 Load `frontend-design-review` in Mode 1 after the UI is runnable, apply only verified targeted findings, and recheck the corrected render.
- [x] 4.4 Rebuild/sign the macOS app and refresh the Desktop shortcut without disturbing persisted local gateway settings or infrastructure data.
- [x] 4.5 Strict-validate the OpenSpec change and mark verified tasks complete.
