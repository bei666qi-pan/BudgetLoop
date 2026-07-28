# Real AI E2E

This suite verifies the complete planning path without mocks:

```text
Chromium -> Next.js same-origin proxy -> FastAPI task-drafts API -> DeepSeek -> schema validation -> rendered review UI
```

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
