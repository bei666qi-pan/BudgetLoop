## Why

BudgetLoop's public release metadata is currently split across Web, backend, macOS, and Windows manifests, while the latest README mixes languages and points at an older artifact set. A single `v0.3.0` release is needed so operators can identify, download, build, and verify the same revision on every supported surface.

## What Changes

- Set the Web package, backend package, macOS bundle, Windows package, Tauri bundle, and Rust crate to version `0.3.0` from one release revision.
- Publish both macOS and Windows desktop artifacts from the immutable `v0.3.0` tag, with checksums and build provenance.
- Make the Windows workflow validate `main` and tagged releases in addition to development branches, and add a macOS release build workflow.
- Rewrite the primary README as an English-first project landing page and provide a separate, complete Chinese README selected from the language switcher.
- Document an accurate platform/version matrix, prerequisites, install paths, local Docker workflow, development workflow, and release verification.
- Include the bounded Agent Team startup progress and failure-recovery fix in the same release.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `cross-platform-release-distribution`: Require one canonical release version across Web, backend, macOS, Windows, documentation, tagged artifacts, and checksums.

## Impact

- Affected areas: package manifests and lockfiles, macOS `Info.plist`, desktop build scripts, GitHub Actions, release documentation, and GitHub Release assets.
- No API contract, database migration, budget-accounting, credential, or sandbox behavior changes are introduced by the release alignment itself.
- Existing Docker Desktop, repository checkout, and provider credential prerequisites remain explicit; desktop launchers do not bundle Docker or secrets.
- Non-goals: redesigning the UI, replacing the execution engine, changing deployment architecture, or claiming a hosted production URL that has not been independently verified.
