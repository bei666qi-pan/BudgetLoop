## Why

The launcher can block indefinitely while macOS attempts an interactive Keychain read during background bootstrap. A locally saved gateway credential must never turn into a repeated authorization gate or prevent the app from reaching its normal foreground settings page.

## What Changes

- Make launcher Keychain reads non-interactive and bounded: an unavailable credential becomes a redacted local configuration state rather than a blocked startup.
- Preserve the web settings page as the only configuration entry point; Keychain remains an implementation detail for this Mac's saved secret.
- Add testable native behavior for an inaccessible legacy item and normal repeated launches.

## Capabilities

### New Capabilities

- `nonblocking-macos-keychain-bootstrap`: Reliable macOS launcher startup when a local Keychain credential cannot be read without interaction.

### Modified Capabilities

- None.

## Impact

- Affected code: native Keychain store, launcher startup behavior, native tests, and macOS package verification.
- Safety: no credential is exposed, written to `.env`, or sent to the browser; no external service or database migration changes.
- Non-goals: creating a shared credential store, automatically bypassing Keychain access controls, or changing the web settings UX.
