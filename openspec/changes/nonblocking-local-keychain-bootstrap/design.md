## Context

The macOS launcher reads the current Mac's saved gateway secret through Security.framework before it starts or refreshes the local compose stack. A legacy Keychain item can require interaction; calling `SecItemCopyMatching` with the default policy from a background queue then blocks startup indefinitely. The foreground web settings page is already the user-owned way to add or replace a credential.

## Goals / Non-Goals

**Goals:**

- Let repeated launches reuse an already-accessible local Keychain item silently.
- Fail quickly and safely when macOS would require Keychain interaction, so the app can open its normal settings page.
- Keep secrets out of browser state, `.env`, logs, and product data.

**Non-Goals:**

- Circumventing a user's Keychain access policy, migrating an inaccessible legacy secret, or replacing the front-end settings flow.

## Decisions

### Prohibit authentication UI and bound automatic bootstrap

The read query uses an `LAContext` with interaction disabled and executes on a serial queue with a one-second launcher wait bound. Some legacy Keychain records can still stall inside Security.framework despite noninteractive context; after the bound expires the launcher treats the credential as unavailable and opens normally. The legacy and app-owned replacement services use separate queues, so one stalled legacy read cannot delay a newly foreground-saved replacement credential.

The underlying synchronous operation is never cancelled (Security.framework does not expose safe cancellation), but it cannot display UI and each service has at most one outstanding read per process. This is preferable to allowing a background startup path to wait indefinitely.

### Keep foreground saving separate

The signed macOS app continues to write new user-entered keys through its origin-scoped web bridge. New generic-password items use `kSecAttrAccessibleAfterFirstUnlock` in an application-owned v2 Keychain service; the v2 entry takes precedence on later reads and is subsequently read without prompting. A legacy item which needs authorization is not read, exposed, modified, or deleted automatically.

## Risks / Trade-offs

- [A legacy item is not automatically reusable] → the app starts reliably and its foreground settings flow gives the user an explicit one-time replacement option.
- [A device is locked] → startup continues without a gateway rather than blocking; the app can use its local non-AI paths until the user unlocks and saves settings.

## Migration Plan

1. Update the native Keychain query and add focused native tests.
2. Let Compose own `.env` parsing and make container-internal database/Redis addresses explicit in the Compose topology, so managed-device tooling cannot stall launcher bootstrap on a native dotfile read; rebuild and sign the local app.
3. Verify the launcher reaches its web window with an unavailable Keychain item, and a normal saved item remains silent on repeated launches.
4. Rollback is a package rollback only; no Keychain data or service data is migrated.

## Open Questions

None.
