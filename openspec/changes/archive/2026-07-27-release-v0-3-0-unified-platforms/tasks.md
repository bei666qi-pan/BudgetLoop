## 1. Version Alignment

- [x] 1.1 Add the canonical `VERSION` file and set every Web, backend, macOS, Windows, Tauri, Rust, and lockfile version to `0.3.1`.
- [x] 1.2 Add an automated release-version parity check and run it in relevant GitHub workflows.
- [x] 1.3 Track the ArtifactStore package and declare LiteLLM/pytest-asyncio so clean Linux backend verification matches local verification.

## 2. Cross-Platform Release Automation

- [x] 2.1 Expand Windows launcher validation to cover `main` while preserving pull-request and development-branch checks.
- [x] 2.2 Add a tag-gated workflow that verifies Web/backend, builds native macOS and Windows artifacts, generates SHA-256 checksums, and publishes the GitHub Release only after all jobs pass.
- [x] 2.3 Make the macOS build emit a versioned archive and verify its embedded bundle version and signature.

## 3. Documentation

- [x] 3.1 Rewrite `README.md` as an English-first landing page with a visible Chinese selector, platform/version matrix, quickstart, capabilities, architecture, prerequisites, and verification guidance.
- [x] 3.2 Rewrite `README.zh-CN.md` as the complete Chinese equivalent with the same version, platform status, prerequisites, and release links.
- [x] 3.3 Add release notes for `v0.3.1` that describe the startup-feedback fix, desktop artifacts, prerequisites, checksums, and known signing limitations.

## 4. Verification and Publication

- [x] 4.1 Run focused and full backend tests, frontend tests/build, version parity, OpenSpec validation, and macOS launcher tests/build checks.
- [x] 4.2 Perform the required post-implementation frontend design review, apply verified targeted corrections, and recheck the corrected UI.
- [x] 4.3 Sync the completed specification and update GitHub `main` without force-pushing.
- [x] 4.4 Tag `v0.3.1`, verify GitHub assets/checksums and the local `BudgetLoop.app`, then archive the completed change on `main`.
