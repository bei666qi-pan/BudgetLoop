# Smart Agent Team fidelity ledger

Reviewed against `concept-smart-team-presets-desktop.png` and
`concept-smart-team-presets-mobile.png` using the runnable application at
`/containers/new`. Final captures are `verified-desktop.png` and
`verified-mobile.png`.

| Area | Result | Evidence / intentional difference |
| --- | --- | --- |
| Visual direction | Match | The implementation keeps the concept's restrained white and pale-blue surfaces, blue primary accent, fine borders, rounded cards and minimal shadows. |
| Primary path | Match | “智能推荐” remains the default path, followed by one goal field, ranked recommendation, editable roles and a persistent create action. |
| Team summary | Match | Desktop keeps a right-hand team preview; mobile converts the same role/token/call facts into a fixed bottom action dock. |
| Role configuration | Improved detail | The concept used compact role rows; the implementation exposes role enablement, independent goal, per-role token cap and execution engine because these are committed product requirements. |
| Open-source provenance | Improved trust | MetaGPT, CrewAI and LangGraph links, reviewed stars and integration type are shown explicitly instead of the concept's single text-only source row. |
| Replaceable engines | Added requirement | OpenHands, Codex, Gemini CLI and OpenCode cards disclose repository, stars, license, source/runtime status and fail-closed behavior. This section was added after the original concept. |
| Mobile responsiveness | Match | At 390 × 844 the document width equals the viewport width; category and role content do not create page-level horizontal overflow, and the action dock remains reachable. |
| Action hierarchy | Match with correction | “一键创建并启动” is primary; unavailable engines disable it and keep “仅创建” available. The original short label “稍后” was changed to “仅创建” after review to avoid implying dismissal. |
| Accessibility | Match | Creation modes and categories use tabs, engine cards expose pressed state, controls have accessible labels, status errors use alerts, and disabled actions remain visibly explained. |
| AI transparency | Improved trust | Recommendation explicitly says it is local and does not call a remote model; creation says no model call occurs beforehand and Skills do not grant permissions. |

## Above-the-fold copy diff

- Concept: “说清目标，系统会为你组合合适的角色与协作方式。”
- Final: “告诉我们项目目标，BudgetLoop 会从经过验证的开源协作模式中组装一支隔离、可审计且有硬预算的团队。”
- Reason: the final copy makes isolation, auditability and budget authority explicit.
- Concept CTA: “为我推荐团队。”
- Final CTA: “智能推荐。”
- Reason: the control sits inside a tab already named “智能推荐”; the shorter label avoids duplicating first-person copy and works on mobile.
- Added disclosure: “本地智能匹配 · 不调用远程模型。”
- Reason: this is a deterministic LangGraph recommendation, so the user should not infer an undisclosed model call.
