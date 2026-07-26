## 1. Native nonblocking bootstrap

- [x] 1.1 Make automatic native Keychain reads fail rather than present or wait for authorization UI.
- [x] 1.2 Preserve the current foreground-only settings save path and add focused source-level/native verification for noninteractive reads.

## 2. Package verification

- [x] 2.1 Rebuild the local app and verify the launcher reaches foreground settings when Keychain access is unavailable.
- [x] 2.2 Run strict OpenSpec validation, Compose validation, package signature verification, and native compilation checks.
