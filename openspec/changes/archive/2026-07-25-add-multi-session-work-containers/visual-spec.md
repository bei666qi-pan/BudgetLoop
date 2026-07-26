## Selected Concepts

- Agent Team overview: `concepts/concept-containers-overview.png` (1506 × 1045)
- Container collaboration workspace: `concepts/concept-container-workspace.png` (1536 × 1024)

Both concepts extend the archived BudgetLoop dashboard direction and are the implementation reference for the new routes.

## Visual Direction

- Character: premium, calm and operational; Gemini-like air and Apple-like restraint.
- Background: true white shell over cold `#F7FAFF`, never cream or warm gray.
- Text: `#0B1F44` primary and `#60759A` supporting text.
- Accent: `#1769F6`; only semantic state uses green, amber or red.
- Geometry: 8–16 px radii, one-pixel cool-blue dividers, minimal cold-blue elevation.
- Typography: Inter/SF-like sans; 32–34 px page title, 20 px selected-session title, 14–15 px body, 13–14 px deliberate control chrome.
- Icons: Lucide-compatible outline icons, about 1.75 px stroke, optically aligned and used only where they clarify an action or state.
- Container model: open rows, rails and section dividers. Do not turn either route into nested card grids.
- Motion: 160–200 ms state transitions for selected rows, hover and composer feedback; disable under reduced-motion preference.

## Component Inventory

- Shared shell: BudgetLoop mark, route-aware navigation, API state and one context-specific primary action.
- Overview: page heading, derived summary strip, search, lifecycle filter, wide container rows and primary row action.
- Workspace: project header, session rail, session row states, chronological transcript entries, explicit handoff object, composer, shared-context section, inbox, runtime/worktree facts and pause action.
- Mobile: preserve the project summary; collapse the three regions into `Session`, `对话` and `上下文` tabs while keeping create/handoff actions reachable.

## Visible-Copy Lock

The first viewport may use the following concepts or their data-backed values: `Agent Team`, `将独立会话组织为可控、可审计的项目团队`, `创建工作容器`, `工作容器`, `运行中的 Session`, `等待处理`, `需要关注`, `搜索工作容器`, `全部`, `活跃`, `已暂停`, `已完成`, `打开团队`, `新建 Session`, `Sessions`, `添加 Session`, `Agent 输出`, `团队上下文`, `收件箱`, `运行与工作区`, `暂停 Session`, `发送消息`, and `创建 Handoff`. New explanatory marketing copy, decorative badges and fake metrics are prohibited.

## Concept-to-Implementation Fidelity Ledger

| Checkpoint | Concept evidence | Required implementation evidence | Status |
| --- | --- | --- | --- |
| Palette | True white/cold-blue canvas, navy text, single blue accent | Browser screenshot and sampled CSS tokens match | Pass — final render uses white/`#F7FAFF`, navy hierarchy and one blue action accent; semantic green/amber/red remain state-only. |
| Overview hierarchy | Heading → summary strip → search/filter → open rows | Desktop overview preserves order and density | Pass — `qa-containers-desktop.png` retains the exact concept sequence and open table density. |
| Workspace regions | 248 px session rail, dominant transcript, ~300 px facts inspector | Desktop screenshot preserves three-region priority | Pass — `qa-container-workspace-desktop.png` preserves the rail/transcript/inspector hierarchy without competing panels. |
| Container model | Rails and dividers; only handoff/composer are framed | No nested-card dashboard introduced | Pass — major regions use continuous surfaces and dividers; framing is reserved for explicit Handoff and input affordances. |
| Typography | Large restrained titles, readable 14–15 px content, deliberate control text | Computed type scale and wrapping inspected | Pass — 32 px page title, 20 px selected-session title and readable 12–15 px operational copy wrap without clipping at tested breakpoints. |
| Collaboration trust | Agent output differs from Handoff; ID and delivery state visible | Transcript semantics and API state verified | Pass — Agent output is explicitly public/non-reasoning; Handoff shows sender, recipient, immutable ID and queued/delivered state. |
| Worktree transparency | Branch, safe relative path and readiness shown together | Runtime inspector uses server data and no false fallback | Pass — readiness, server branch and `.budgetloop/worktrees/...` relative path are displayed together; missing/error data is not replaced with a false ready path. |
| Responsive behavior | Structure designed to collapse into three mobile tabs | 390 px capture has no overflow and actions remain reachable | Pass — native 390 × 844 IAB check reported `scrollWidth === innerWidth === 390`; Session/对话/上下文 tabs and primary actions remain reachable. |
| Interaction | Selected Session, filter, composer and handoff mode have clear state | Browser click path and focus behavior verified | Pass — filters, Session switch, mobile tabs, composer/Handoff submission feedback and Escape-close dialog behavior were exercised. |
| Copy | Only locked product labels and data-backed values | Above-the-fold diff has no invented copy | Pass — structural labels match the lock; concept sample counts/roles were replaced only by API-backed mock values, with no decorative metrics or marketing copy added. |

## Final Review Record

- Mode 1 design review covered user paths and action hierarchy, design-token compliance, accessibility, responsive behavior and trustworthy collaboration/worktree states.
- Corrected findings: duplicate primary actions, `/containers/new` route classification, 1024 px composer overflow, state-dot semantics, tab/tabpanel relationships, shared-context accessible naming, Handoff submission feedback, Escape-close behavior and nested `main` semantics.
- Final Browser/IAB evidence: desktop and native 390 × 844 paths loaded; mobile tabs switched; `scrollWidth` remained 390; console contained no warnings or errors.
- Copy diff: concept-only sample quantities (`3` containers, `6` Sessions and similar examples) resolve to returned API values in implementation; locked action and section labels remain unchanged.

## ImageGen Record

Built-in ImageGen produced both project-bound concepts. The overview prompt requested the full Agent Team list with real lifecycle/session/workspace fields and prohibited fake metrics or card grids. The workspace prompt requested the complete three-region collaboration surface with explicit Agent output, immutable handoff IDs, delivery state, shared context and worktree facts; it prohibited hidden reasoning, unrestricted agent calls and auto-merge UI.
