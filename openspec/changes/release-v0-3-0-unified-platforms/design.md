## Context

The repository already builds a Next.js Web UI, Python control plane, native Swift macOS launcher, and Tauri Windows launcher, but each manifest independently declares `0.2.0`. The existing Windows workflow validates feature branches only, the macOS archive is built locally, and the two README languages do not yet provide one release-oriented entry point. The startup-feedback fix is implemented and validated on a branch that now needs to ship from the current `main` revision.

The first immutable candidate tag, `v0.3.0`, correctly stopped before publication when a clean Linux runner found that the broad `artifacts/` ignore rule excluded `backend/app/artifacts` and the declared dev extras omitted LiteLLM and pytest-asyncio. The corrected release is `v0.3.1`; the failed tag is not moved or represented as a published release.

The documentation hierarchy follows the concise landing-page pattern used by established coding-agent projects, especially [OpenHands/OpenHands](https://github.com/OpenHands/OpenHands) (82k+ stars when reviewed) and [cline/cline](https://github.com/cline/cline) (65k+ stars): centered identity, visible install choices, short value proposition, proof-oriented capabilities, then deeper architecture and development details. BudgetLoop retains its own visual identity and avoids copying project-specific claims.

## Goals / Non-Goals

**Goals:**

- Make `VERSION` the declared release value and verify every package/bundle manifest against it.
- Deliver Web, backend, macOS, and Windows from the same immutable `v0.3.1` revision.
- Gate release publication on backend, frontend, version, macOS, and Windows checks.
- Publish versioned desktop artifacts and SHA-256 checksums on the GitHub Release.
- Make `README.md` fully English-first and `README.zh-CN.md` a complete Chinese equivalent with reciprocal language links.
- Make local `BudgetLoop.app` a freshly built `0.3.1` bundle from the released source.

**Non-Goals:**

- Bundling Docker Desktop, a repository checkout, model credentials, or database contents into either launcher.
- Introducing automatic application updates, installer signing/notarization, or a hosted SaaS endpoint.
- Changing product architecture, database schema, budget behavior, or provider credential boundaries.

## Decisions

### Canonical version plus an executable parity gate

A root `VERSION` file will contain `0.3.1`. A Python standard-library validation script will compare it with the Web and Windows `package.json`/lockfiles, backend `pyproject.toml`, macOS `Info.plist`, Tauri configuration, and Rust package metadata. CI and release workflows will run this gate.

This is preferred over relying on human review because package ecosystems still require their native version fields. A build-time rewriting tool was considered, but rejected for this release because it would mutate source inputs during packaging and obscure provenance.

### One tagged release workflow with native runners

One Git tag triggers a workflow with an Ubuntu verification job, a macOS native build job, a Windows native test/MSI job, and a final publication job. The final job downloads only artifacts produced by the tagged run, generates checksums, and creates the GitHub Release after every gate passes.

This is preferred over manually uploading locally built files because a local macOS archive plus a separate branch-built Windows artifact can drift from the tag. Existing branch/PR Windows validation remains as fast pre-release feedback.

### Release documentation as a product landing page

The README will prioritize an immediate platform matrix and quickstart, then explain the closed loop, safety boundaries, architecture, development, and verification. English and Chinese are separate files so GitHub first renders English without duplicating the full document inline. Both pages point at `releases/latest` and state prerequisites instead of hard-coding assumptions about bundled dependencies.

### Local app is rebuilt from the release candidate

The macOS build script will derive the archive version from `Info.plist`, compile/sign the local bundle, copy it to the repository root, and emit a versioned zip. Local verification will inspect the installed bundle's version, codesign status, and archive contents.

## Risks / Trade-offs

- **[Unsigned or locally signed macOS app can trigger Gatekeeper]** → Document that `v0.3.1` is not Apple-notarized and provide the source-build path; do not imply notarization.
- **[Windows MSI cannot be faithfully built on macOS]** → Treat `windows-latest` GitHub Actions as the authoritative build gate and download its tagged artifact for the Release.
- **[Tag workflow failure could leave a tag without a published Release]** → Do not describe the release as complete until the tagged workflow succeeds and assets/checksums are visible.
- **[Local developer environments can mask undeclared files or dependencies]** → Verify on a clean Linux tag runner, scope runtime ignores to the repository root, and declare every backend test dependency.
- **[Multiple native manifests can drift later]** → Run the parity script on `main`, pull requests, and tag publication.
- **[Direct `main` update may race remote changes]** → Fetch immediately before integration and use a normal fast-forward push; never force-push.

## Migration Plan

1. Integrate the startup-feedback fix onto current `origin/main`.
2. Update all native version fields and add the parity gate.
3. Add/adjust branch validation and tagged cross-platform release workflows.
4. Rewrite and validate both README documents and `v0.3.1` release notes.
5. Run local backend, frontend, macOS, and release-version verification.
6. Push the verified commit to `main`, create the immutable `v0.3.1` tag, and wait for the tag workflow.
7. Confirm the Release assets, checksums, workflow evidence, and local `BudgetLoop.app` version.

Rollback is a normal follow-up commit on `main`; the immutable tag and Release remain as historical evidence. A broken unpublished tag is not moved—use a corrected patch release instead.

## Open Questions

None for `v0.3.1`. Apple notarization and Windows code signing remain future release-hardening work.
