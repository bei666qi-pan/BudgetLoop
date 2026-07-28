# Real AI E2E

This suite verifies the complete planning path without mocks:

```text
Chromium -> Next.js same-origin proxy -> FastAPI task-drafts API -> DeepSeek -> schema validation -> rendered review UI
```

## Cross-platform coverage

BudgetLoop Web, macOS, and Windows use the same Docker-backed `web`, `control-plane`, and AI gateway services. The real-model browser E2E therefore validates the shared application chain used by all three surfaces.

| Surface | What this suite validates | Additional platform gate |
| --- | --- | --- |
| Web | Next.js UI, same-origin BFF, FastAPI planning API, real DeepSeek response, schema validation, and rendered AI provenance | `npm test` and `npm run build` in `web/` |
| macOS | The same Web/control-plane/AI chain launched by the native AppKit host | `./desktop/build.sh`, bundle version parity, and `codesign --verify` in `release.yml` |
| Windows | The same Web/control-plane/AI chain launched by the Tauri/WebView2 host | Rust tests and MSI creation in `release.yml` |

This test does not replace native packaging checks. A release is considered cross-platform verified only when the real AI E2E and the existing Web, macOS, and Windows release gates all pass.

## Required secret

Create a GitHub Actions repository secret named `DEEPSEEK_API_KEY`. The workflow passes it only through the runner environment and a mode-0600 temporary `.env` file. The value is never committed, printed, uploaded, or returned to the browser.

The workflow intentionally fails when the secret is absent. It also fails when BudgetLoop returns `local_fallback`, even if the page still displays a usable locally generated draft.

## Provider configuration used by CI

- Gateway type: `compatible`
- Base URL: `https://api.deepseek.com`
- Model: `deepseek-v4-flash`
- Secret variable: `DEEPSEEK_API_KEY`

## Assertions

The browser test requires all of the following:

- gateway preflight is healthy;
- public gateway status contains no API key;
- `/api/task-drafts` returns HTTP 200;
- `provenance.source` is `ai`;
- `provenance.model` is `deepseek-v4-flash`;
- `provenance.fallback_reason` is null;
- the AI response passes BudgetLoop's trusted schema and preset validation;
- the page displays `AI 建议 · 已校验` and never displays the local fallback label.

## Local execution

Start BudgetLoop with the same compatible gateway variables, then run:

```bash
cd e2e
npm install
npx playwright install chromium
E2E_BASE_URL=http://127.0.0.1:3000 E2E_MODEL=deepseek-v4-flash npm test
```

Do not place provider keys in shell history, screenshots, test fixtures, or committed `.env` files.
