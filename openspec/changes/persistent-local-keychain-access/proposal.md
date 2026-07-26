## Why

The macOS launcher currently shells out to the `security` CLI for every launch and is ad-hoc signed by default. That prevents macOS from associating repeated Keychain requests with one stable BudgetLoop identity, causing repeated authorization prompts.

## What Changes

- Read the local gateway credential through the native macOS Security framework rather than an external command.
- Keep the web settings page as the only user-facing configuration surface. In the packaged Mac app, save a user-submitted gateway configuration directly to the local app host; browser callers retain the existing authenticated API path.
- Prefer a stable, local code-signing identity for packaged launcher builds; retain explicit ad-hoc fallback when no identity is configured.
- Create a one-time local signing identity on this Mac so the application can be recognised consistently after rebuilds.

## Capabilities

### New Capabilities

- `persistent-macos-keychain-access`: Native, least-privilege Keychain access with stable local app identity and first-use-only authorization behavior.

### Modified Capabilities

- None.

## Impact

- Affected code: `desktop/Sources/LauncherCore.swift`, `desktop/Sources/Windows.swift`, `desktop/Sources/NativeGatewaySettingsStore.swift`, `web/app/settings/ai/page.tsx`, `desktop/build.sh`, and local macOS Keychain signing identity.
- Safety: the API key remains Keychain-only and is still injected only into launcher child processes; no API contract or data migration changes.
- Non-goals: disabling macOS prompts, broadening filesystem access, writing the secret to `.env`, or altering Docker/AI routing.
