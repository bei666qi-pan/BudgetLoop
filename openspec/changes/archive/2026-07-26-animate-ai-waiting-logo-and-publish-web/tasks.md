## 1. Branded waiting activity

- [x] 1.1 Replace the shared B/orbit indicator with a reference-faithful double-loop SVG disturbance component and token-based full/compact CSS motion.
- [x] 1.2 Add focused component tests for accessible status naming, shared waiting-state use and reduced-motion/static styling hooks.

## 2. Browser project upload

- [x] 2.1 Add bounded authenticated multipart folder-snapshot storage with path, duplicate, file-count, per-file and aggregate-size validation plus partial-upload cleanup.
- [x] 2.2 Thread an opaque upload identifier through team creation and seed each isolated workspace from the validated snapshot without changing full-access semantics.
- [x] 2.3 Add backend tests for valid upload/seed behavior and rejection of traversal, oversized, missing and full-access-combined uploads.
- [x] 2.4 Add normal-browser folder upload controls, progress/success/error feedback and request typing while preserving the native macOS picker flow.
- [x] 2.5 Add frontend tests for browser upload, native picker distinction, recoverable errors and submitted upload identifiers.

## 3. Production credential and deployment boundary

- [x] 3.1 Add a bounded same-origin Next.js control-plane proxy and migrate browser API/event calls away from public tokens.
- [x] 3.2 Add production Coolify Compose configuration, domestic Docker/npm sources, health checks and environment documentation for the web, control-plane, worker, Postgres and Valkey services.
- [x] 3.3 Add proxy/security tests and verify that production bundles and tracked files contain no provider or control-plane secret.

## 4. Verification and UI review

- [x] 4.1 Run targeted backend/frontend tests, full frontend tests, production build, backend suite and strict OpenSpec validation.
- [x] 4.2 Run the required Mode 1 frontend design review on the runnable UI, apply targeted verified findings and recheck desktop/mobile and reduced-motion behavior.

## 5. Publish and deploy

- [x] 5.1 Create the initial Git history safely, publish the feature branch to GitHub, open a scoped PR, pass gates and squash-merge to `main`.
- [x] 5.2 Create/update the public Gitee mirror, configure the Coolify service and server-only DeepSeek/model variables, bind `budgetloop.versecraft.cn` and deploy.
- [x] 5.3 Poll deployment and service health, then verify the public homepage, same-origin health, folder upload and bounded AI draft generation before reporting completion.
