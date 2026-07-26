## Context

The web application has a hand-drawn double-loop header mark and no branded metadata icon. macOS and Windows already ship platform-native BudgetLoop icons, but macOS reports `1.0` while Windows and the web package report `0.1.0`. The next source revision also contains accumulated, verified product work that must be distributed together rather than leaving platform binaries attached to an older commit.

The established visual source is `desktop/Resources/BudgetLoop.svg`: a blue interlocking-loop mark on a light rounded-square field. The release must keep the existing local-Docker model; native installers are launchers, not bundles of Docker Desktop, model providers, source code, or user secrets.

## Goals / Non-Goals

**Goals:**

- Use one recognizable BudgetLoop mark in the persistent web header, web metadata, macOS app, and Windows MSI.
- Release one semantically versioned source revision (`0.2.0`) with explicit Windows and macOS assets.
- Make each release asset traceable to its source commit and checksum, and retain build/test evidence.
- Preserve existing launcher prerequisites and data-preserving refresh behavior.

**Non-Goals:**

- Do not redesign the web information architecture or replace platform-native icon packaging.
- Do not embed Docker, provider credentials, or a model runtime in either native installer.
- Do not introduce automatic application updating, code signing, a new download host, or a new API.

## Decisions

### D1: Reuse the established vector geometry as the canonical mark

The web header and Next.js icon use a small static SVG that reproduces the existing two-loop geometry and semantic colors. macOS continues using the generated `.icns`; Windows continues using Tauri's `.ico`/`.png`. This keeps the native shell formats correct while making the visible web identity match. A raster web logo was rejected because it is less crisp at header and favicon sizes; importing the macOS `.icns` into the browser is not portable.

### D2: Release `0.2.0` from a single tagged commit

`0.2.0` is the first release after `0.1.0` to include user-visible behavior, desktop resilience work, and the website branding update. `web/package.json`, Windows Tauri/package metadata, and macOS bundle versions all carry `0.2.0`; the Git tag is `v0.2.0`. A GitHub Release attaches the macOS zip and Windows MSI built from that tag. Checksums are included in the release body.

### D3: Use existing build tooling as release gates

The web uses its existing test/build commands. macOS uses `desktop/build.sh`, and Windows uses the existing GitHub Actions workflow plus its Windows runner validation. The release is created only after those artifacts identify the same version and the packaged icons are present. This is a release process, not a change to the budget or sandbox control plane.

## Risks / Trade-offs

- [Unsigned macOS bundle shows Gatekeeper friction] → document that the archive is ad-hoc signed and retain the existing Developer ID build option.
- [Windows and macOS builds are platform-specific] → use the Windows CI runner for MSI verification and local macOS build for the archive; attach both outputs with their checksums.
- [A browser favicon differs from the installer artwork] → derive both from the same interlocking-loop geometry and verify by inspecting each rendered/icon asset.
- [Mixed worktree accidentally publishes unrelated files] → stage the explicitly reviewed release scope only after tests complete, then inspect the staged diff before commit.

## Migration Plan

1. Add the reusable web mark and SVG metadata icon; align all package versions to `0.2.0`.
2. Run frontend tests/build, macOS build, Windows workflow/tests, and inspect the resulting icons.
3. Stage the reviewed current release scope, commit the versioned revision, and push it to GitHub.
4. Tag the commit `v0.2.0`, upload macOS and Windows artifacts, include checksums and prerequisites, then verify the public release page and web deployment revision.
5. Roll back by repointing the public web deployment and publishing/retaining the prior `v0.1.0` release; local launcher state and data volumes are untouched.

## Open Questions

None. The release uses the repository's existing Docker-backed launcher distribution model.
