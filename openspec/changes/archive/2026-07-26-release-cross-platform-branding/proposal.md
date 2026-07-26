## Why

The current working tree contains the next set of verified product updates, but the web, macOS launcher, Windows launcher, and public GitHub release do not yet present one coherent version or visual identity. Operators need a single, traceable release whose download assets and in-product branding match the current web experience.

## What Changes

- Publish the verified current updates as one versioned GitHub release, with matching source revision and platform assets.
- Add the BudgetLoop interlocking-loop brand mark to the web application shell and web metadata assets, while retaining the existing macOS and Windows application icons.
- Align the macOS launcher version with the Windows/web release version and rebuild the macOS archive from the released revision.
- Rebuild and validate the Windows MSI from the same revision, retaining its branded Tauri icon.
- Document the version, asset checksums, prerequisites, and validation evidence in the GitHub release notes.

## Capabilities

### New Capabilities

- `cross-platform-release-distribution`: A traceable GitHub release that distributes the same verified revision for web, macOS, and Windows.

### Modified Capabilities

- `frontend-experience-system`: The persistent web application shell and web metadata expose the BudgetLoop brand mark.
- `mac-app-launcher`: The macOS launcher package has a release-aligned version and BudgetLoop icon.
- `windows-local-launcher`: The Windows MSI remains version-aligned and carries the BudgetLoop icon.

## Impact

- Affects the Next.js layout/application shell and static metadata assets, macOS `Info.plist` and build output, Windows Tauri package metadata/assets, README release links, GitHub release notes, and CI release validation.
- Does not change model credentials, budget accounting, task APIs, sandbox permissions, or database schema.
- Existing installations may continue using prior release assets; no data migration is required.
