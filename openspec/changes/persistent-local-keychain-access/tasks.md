## 1. Native credential access

- [x] 1.1 Replace the launcher subprocess Keychain read with a redacted Security.framework lookup.
- [x] 1.2 Preserve existing gateway failure handling when the native read is denied or unavailable.
- [x] 1.3 Add an origin-scoped native bridge so the web settings page can save redacted configuration locally without receiving the key back.

## 2. Stable local identity

- [x] 2.1 Make the packager prefer a named local signing identity with an ad-hoc fallback.
- [x] 2.2 Create the one-time local signing identity in this user's login keychain and rebuild the app with it.

## 3. Verification

- [x] 3.1 Verify the app's signing identity, Keychain lookup path, redaction boundaries, and strict OpenSpec validation.
- [x] 3.2 Verify the foreground save flow in the packaged app and the browser fallback flow.
