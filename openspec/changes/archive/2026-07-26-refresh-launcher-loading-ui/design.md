## Context

The native launcher currently uses a fixed 480×240 AppKit window containing a spinner, text field, and hidden quit button. Startup status already arrives through `LauncherDelegate`, so the visual experience can improve without changing Docker, AI, or gateway behavior. The supplied mark is a simple blue interlocking loop and is reproduced as a local SVG then compiled into an `.icns` bundle resource.

## Goals / Non-Goals

**Goals:**
- Present a calm, high-quality loading experience that makes long local startup feel intentional.
- Make the current launcher state legible at a glance, with progress continuity and a useful failure recovery state.
- Ship a crisp vector-derived application icon at all macOS icon sizes.
- Respect reduced motion and keep status information redacted.

**Non-Goals:**
- Do not alter compose lifecycle, Docker health semantics, provider configuration, or web routes.
- Do not add runtime rendering dependencies, web content, or provider credentials to the native UI.

## Decisions

### D1: AppKit-native loading composition
Use AppKit layers and `NSVisualEffectView`/native controls rather than embedding a separate local web page. The launcher already owns an AppKit window, so this preserves a fast pre-Docker startup path and avoids a second frontend runtime.

### D2: Vector source plus `.icns` output
Keep `desktop/Resources/BudgetLoop.svg` as the editable source and generate `BudgetLoop.icns` during packaging. The vector tracks the supplied interlocking-loop geometry; `.icns` is required by Finder and the Dock. A raster-only source would be less adaptable across macOS icon sizes.

### D3: Stateful but non-deceptive progress
Map known launcher status text into a bounded set of visual stages. The stage treatment is indeterminate (no fabricated percentage) and the exact status text remains visible. Failure switches to a readable recovery panel and a clear quit action.

### D4: Motion and accessibility
Use subtle layer opacity/scale transitions and a restrained spinner only while active. Reduce motion when macOS accessibility settings request it; preserve text contrast and accessible labels for the mark, activity, state, and exit action.

## Risks / Trade-offs

- [Status strings evolve] → stage matching has a neutral fallback and always presents the original safe status string.
- [New asset is omitted from a manual bundle] → `build.sh` copies the `.icns` deterministically and signature validation remains required.
- [Animated waits fatigue users] → animation is deliberately low-amplitude and reduced-motion safe.

## Migration Plan

1. Add the vector source, generated icon resource, bundle key, and loading layout.
2. Rebuild and re-sign `BudgetLoop.app`; existing shortcuts continue pointing to the same bundle path.
3. Roll back by restoring the prior AppKit layout and removing the icon resource; no persistent data changes occur.

## Open Questions

None.
