## Context

`LauncherCore.bootstrapGateway()` invokes `/usr/bin/security find-generic-password -w` on every launch. The bundle is ad-hoc signed, and this Mac has no valid signing identity. Native Keychain Services lets the actual app request the existing generic-password item; a stable local signing identity lets macOS recognise that app after rebuilds.

## Goals / Non-Goals

**Goals:**
- Present the Keychain authorization once to the BudgetLoop app and reuse macOS's persisted decision.
- Keep the upstream key out of `.env`, source, logs, and browser code.
- Use a local, non-distribution code-signing identity that survives app rebuilds.
- Keep the existing web page as the foreground configuration surface for every user.

**Non-Goals:**
- Bypass the first Keychain authorization, suppress macOS security UI, or weaken TCC/Keychain ACLs.
- Share the local identity or API key with other users or machines.
- Return the submitted API key to browser JavaScript or write it to localStorage, `.env`, or the Docker container filesystem.

## Decisions

### D1: Native Security.framework read
Use `SecItemCopyMatching` with exact account/service attributes and `kSecReturnData`; handle only status codes and never log the returned bytes. This binds the request to the signed BudgetLoop app instead of its external `security` subprocess.

### D1a: Foreground settings bridge
The existing `AI 网关与应用继承` page remains the configuration entry point for every user. When rendered inside the packaged `WKWebView`, an allowlisted `localhost:3000` native message bridge accepts a save action only from the main BudgetLoop frame. The app stores non-secret settings in its local Application Support configuration and the submitted key in Keychain, then returns only redacted settings to the page. The browser/API flow remains available outside the packaged app.

### D2: Stable local signing identity
Generate a self-signed, code-signing-only identity named `BudgetLoop Local Signing` in the login keychain once on this Mac. `desktop/build.sh` prefers that identity when present and explicitly falls back to ad-hoc signing for contributors who have not installed it.

### D3: Preserve user control
The first native read remains an OS-controlled authorization event. The user must choose the persistent approval option in that macOS dialog; changing the local Keychain item or signing identity can legitimately cause a new prompt.

## Risks / Trade-offs

- [Local identity expires or is removed] → build falls back safely to ad-hoc signing and reports the chosen identity.
- [First-use prompt is denied] → launcher shows its existing guided gateway state; no fallback secret store is created.
- [Self-signed identity is mistaken for distribution signing] → it is local-only, never notarized, and documented as such.

## Migration Plan

1. Generate/import the local signing identity into this Mac's login keychain.
2. Rebuild the app with that identity and use native Keychain access.
3. On first launch, approve BudgetLoop in the standard Keychain prompt; later launches reuse the decision.
4. Roll back by removing the identity and rebuilding ad-hoc; the gateway secret remains unchanged in Keychain.

## Open Questions

None.
