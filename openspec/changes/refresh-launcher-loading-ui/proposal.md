## Why

BudgetLoop's macOS launcher currently opens with a plain spinner and a dense status label, even though startup can take several minutes while Docker and local services become ready. The desktop shortcut also needs a recognisable product mark, based on the supplied loop motif, so the app is easy to identify and trust.

## What Changes

- Add a production SVG version of the supplied blue interlocking-loop mark and package it as the macOS app icon.
- Replace the bare native startup window with an airy, progressive loading experience: branded mark, readable current step, calm progress treatment, contextual safety text, and an accessible error state.
- Keep the waiting experience responsive and respectful of reduced motion; no gateway key or diagnostic secret is shown.

## Capabilities

### New Capabilities

- `macos-launcher-loading-experience`: The branded, accessible macOS launcher waiting and failure states, including the packaged application icon.

### Modified Capabilities

- None.

## Impact

- Affected code: `desktop/Sources/Windows.swift`, `desktop/Info.plist`, `desktop/build.sh`, and launcher resources.
- APIs and budgets: no API, AI model, or budget-contract changes.
- Safety: status copy remains redacted; no Keychain secret reaches UI, assets, logs, or source.
- Migration: additive local app-bundle assets only; existing app launches and settings remain compatible.
- Non-goals: no execution-engine, Docker lifecycle, gateway routing, or web information-architecture redesign.
