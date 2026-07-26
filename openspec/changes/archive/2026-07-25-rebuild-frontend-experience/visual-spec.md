# Frontend Experience Inventory and Visual Specification

## Route and Workflow Inventory

### `/` — Operator workspace

- Source data: `GET /api/tasks`, latest run summary per task, API health.
- Primary action: `新建任务`.
- Required visible states: loading, API failure with retry, no tasks, no filter matches, populated task list.
- Required task information: task name/id/template, latest run status, iteration, token usage, cost when configured, and continuation link.
- Core workflow: discover or filter a task → open its latest run; or create a new task.

### `/new` — Guided task creation

- Submission: `POST /api/tasks` with idempotency key; success returns `run_id` and navigates to the run.
- Intent fields: task template, name, description, acceptance criteria.
- Workspace/safety fields: work directory and high-risk approval requirement.
- Strategy and budget fields: strategy, token limit, wall-time limit, active-runtime limit, call limit, cost limit, parallel-call limit.
- Required states: pristine, inline-invalid, submitting, server/network failure with preserved input, successful navigation.
- Core workflow: describe intent → confirm workspace/safety → choose recommended budget or edit advanced limits → review → start task.

### `/runs/[id]` — Run command center

- Source data: run aggregate, LLM calls, budget details, events/stream, approval events.
- Primary state: status, current phase, pressure, iteration, active runtime, terminal versus live, connection/refresh state.
- Budget state: used/reserved/remaining/limit for tokens, calls, cost and timing where available; phase allocations and reallocations.
- Diagnostics: timeline/events, LLM calls and filters, budget breakdown, run/task metadata.
- Actions: pause, cancel, approval approve/reject/modify, open final report when terminal.
- Required states: initial load, active/live, waiting approval, connection degraded, partial data, terminal, retryable API/action failure.
- Core workflow: understand current activity → inspect budget health → handle approval or control run → inspect diagnostics → open report.

### `/runs/[id]/report` — Outcome report

- Source data: final report plus authenticated JSON/Markdown export endpoints.
- Primary state: terminal outcome and acceptance result.
- Evidence: iterations, runtime, tokens, cost, calls, average progress, criteria/test result, changed files/diff, strategy switches, issues and suggestions.
- Required states: loading, report pending/unavailable, completed, partially completed, budget exhausted, failed, export failure.
- Core workflow: understand outcome → inspect achieved/unresolved work → inspect evidence → export or return to run.

## Product Journey

`任务工作台 → 配置任务 → 实时监督 → 结果复盘`

The shell keeps this lifecycle visible. Primary actions advance the lifecycle; secondary diagnostics never compete with them.

## Visible Copy Lock

- Global: `BudgetLoop`, `任务`, `新建任务`, `API 已连接` / `API 不可用`.
- Workspace: `任务工作台`, `创建并监督每一次预算内执行`, `搜索任务`, `全部`, `运行中`, `待处理`, `已完成`, `需关注`, `继续监督`, `查看结果`.
- Creation: `配置任务`, `定义目标`, `工作区与安全`, `预算策略`, `确认并启动`, `启动任务`.
- Run: `运行指挥台`, `实时执行`, `当前活动`, `预算健康`, `事件时间线`, `模型调用`, `阶段预算`, `运行信息`, `暂停`, `取消运行`, `查看最终报告`.
- Report: `执行结果`, `验收通过`, `部分完成`, `预算已耗尽`, `验收未通过`, `完成了什么`, `资源使用`, `修改的文件`, `仍需处理`, `后续建议`, `导出 JSON`, `导出 Markdown`.
- No hero eyebrow, decorative badge, fake claim, or speculative metric is permitted.

## Concept Direction

- Theme: calm high-trust light operations console; near-white and ice-blue backgrounds with subtly translucent white work surfaces and precise material depth.
- Typography: modern neutral sans for content/UI, monospaced identifiers and diagnostic values; no essential text smaller than 12px.
- Accent: premium azure/cornflower blue with a restrained blue-violet edge for primary actions and healthy progress; amber for constrained/attention; coral red for critical/destructive; slate blue for neutral information.
- Container model: fixed responsive shell, open content bands, thin divider rails, one strong summary frame per route, contained tables only where data requires them; avoid nested card grids.
- Signature motifs: vertical lifecycle rail, thin blue budget progress tracks, soft square-dot status marks, quiet line icons, monospace resource values, and very subtle frosted material panels.
- Motion: short status/section reveal and live-indicator pulse only; fully suppressed for reduced-motion users.
- Responsive: desktop concept target 1440×1000; mobile target around 390px uses single-column reading order, sticky/bottom-safe primary action where useful, and contained horizontal scrolling for tables.

## Icon Inventory

- Brand: loop/infinity mark with one interrupted segment indicating controlled iteration.
- Navigation: workspace/list, plus, activity/pulse, report/document.
- Status: filled dot or small ring paired with text; check-circle, alert-triangle, x-circle only for terminal semantics.
- Actions: arrow-right, pause, square/stop, refresh, download, search, chevron, close.
- Budget: tokens/hash, clock, dollar, calls/layers; use consistent 1.75–2px rounded outline stroke and 16–18px optical size.
- Approval: shield-alert for request, check for allow, pencil for modify, x for reject.

## Concept Asset Inventory

- `concept-dashboard.png`: populated operator workspace, filter controls, task rows, empty/error treatments implied by the component system.
- `concept-create.png`: complete guided creation page with all field groups and review action.
- `concept-run.png`: active run command center showing pressure, budgets, timeline, diagnostics and an approval request.
- `concept-report.png`: partially completed outcome report showing the full evidence hierarchy.

Concept images are visual specifications only. All real UI text, controls, charts, data, and icons remain code-native.

## Extracted Design System

- Color lock: page background `#f7faff` with a faint cool-blue cast; primary surface `rgba(255,255,255,.88)`; raised surface `#ffffff`; text `#0b1f44`; secondary text `#60759a`; border `#d8e4f5`; strong border `#bed2ee`; primary `#1769f6`; primary hover `#0d57d9`; soft primary `#edf4ff`; informational blue `#2f7df6`; success `#0cad72`; warning `#f28a00`; critical `#ef4b5b`.
- Shadow lock: cool, low-opacity elevation only—`0 10px 30px rgba(35, 89, 160, .08)` for primary surfaces and `0 4px 14px rgba(35, 89, 160, .06)` for controls. No glow.
- Radius scale: 8px controls, 12px panels, 16px one-off summary surfaces; full pills only for semantic status and switches.
- Spacing scale: 4, 8, 12, 16, 20, 24, 32, 40, 56px. Desktop page gutters 32px; content max width 1440px; mobile gutters 16px.
- Typography: Inter/system sans, weight 400–700; page title 32–38px/1.15; section title 18–20px/1.3; body 14–16px/1.6; controls 14px/1.25; metadata minimum 12px/1.45. JetBrains Mono/system mono for IDs, paths, resource values and code.
- Containers: one quiet sticky top shell; open route canvas; one composed summary surface; thin section rails; data table/list when row comparison matters; disclosures for optional evidence. Avoid nested panels beyond one level.
- Interaction: 44px minimum primary control height, 40px compact control height, visible 3px soft-blue focus ring, 160–220ms ease-out transitions, active/live pulse only when status is genuinely live.
- Mobile: top navigation becomes compact brand + primary action; filters scroll within their own rail; task rows become labelled stacked rows; creation/review columns become one reading flow; run summary/budget/approval precede diagnostics; wide diagnostics scroll inside bounded regions; report outcome/actions precede evidence and resources.

## Concept Acceptance Notes

- Accepted dashboard excludes the rejected sidebar concept and contains only existing lifecycle navigation.
- Accepted creation concept keeps every API-supported field visible and uses a local step indicator, not a server-side wizard.
- Accepted run concept prioritizes status, activity, budget and approval before timeline/model diagnostics.
- Accepted report concept uses partial completion to define truthful achieved-versus-unresolved hierarchy.
- In-image sample dates, identifiers, model names and metrics are illustrative only; runtime values always come from the API.
