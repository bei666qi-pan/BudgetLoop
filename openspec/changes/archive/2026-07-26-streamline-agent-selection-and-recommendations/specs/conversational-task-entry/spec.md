## MODIFIED Requirements

### Requirement: Explainable graceful fallback
The draft service SHALL first attempt the configured bounded AI path when it is enabled and configured, SHALL give reasoning-enabled models a separate capped planning timeout, SHALL fall back to deterministic local recommendation only when that attempt is unavailable or invalid, and SHALL disclose compact public provenance without making fallback a creation blocker.

#### Scenario: AI draft succeeds
- **WHEN** a healthy configured gateway produces a valid draft within the planning bound
- **THEN** the response identifies `ai` provenance, the safe model alias, the selected preset, and concise public match reasons or signals

#### Scenario: Maximum-effort compatible model needs more than generic health timeout
- **WHEN** a configured reasoning-enabled compatible model remains reachable but takes longer than the generic gateway read timeout to return valid structured output
- **THEN** the recommendation request remains active within its longer capped planning timeout and the system does not prematurely report local fallback

#### Scenario: AI draft is unavailable
- **WHEN** AI is disabled, unconfigured, exceeds the capped planning timeout, is unreachable, is rejected, or returns invalid bounded output
- **THEN** the response identifies `local_fallback`, includes a sanitized fallback code, and still provides a usable trusted-catalog draft

## ADDED Requirements

### Requirement: Task-aware execution-engine choice
The conversational draft SHALL classify trusted recommended work as `coding` or `general`, SHALL recommend Codex for coding work and OpenHands for all other work, and SHALL let the operator explicitly choose an available OpenHands, Codex, or Gemini CLI engine before creation.

#### Scenario: Coding draft receives smart default
- **WHEN** a new draft resolves to coding work and the operator has not selected an engine
- **THEN** Codex is the recommended and selected execution engine

#### Scenario: Non-coding draft receives smart default
- **WHEN** a new draft resolves to non-coding work and the operator has not selected an engine
- **THEN** OpenHands is the recommended and selected execution engine

#### Scenario: Operator chooses an engine
- **WHEN** the operator explicitly selects an available OpenHands, Codex, or Gemini CLI engine
- **THEN** that selection takes precedence, survives follow-up refinement, applies to enabled roles, and is persisted in the creation snapshot

#### Scenario: Selected engine is unavailable
- **WHEN** registry preflight reports that an engine runtime is unavailable
- **THEN** the interface shows a concise readiness reason, prevents invalid confirmation, and does not silently substitute another engine

### Requirement: Reliable conversational submission
The home composer SHALL use one submission path for keyboard and button activation and SHALL preserve multiline and input-method behavior.

#### Scenario: Operator presses Enter
- **WHEN** the composer has meaningful text, is idle, is not in IME composition, and the operator presses Enter without Shift
- **THEN** the composer submits exactly once

#### Scenario: Operator inserts a newline
- **WHEN** the operator presses Shift+Enter
- **THEN** the composer inserts a newline without submitting

#### Scenario: Input method is composing
- **WHEN** Enter is used to confirm an IME composition or the composer is empty or busy
- **THEN** no draft submission is triggered

### Requirement: Branded accessible planning feedback
The conversational entry SHALL show the BudgetLoop vector mark with restrained orbit/morph motion while planning or creating, SHALL expose a readable status to assistive technology, and SHALL honor reduced-motion preferences.

#### Scenario: Agent planning is in progress
- **WHEN** draft generation or confirmed team creation is pending
- **THEN** the interface shows the animated BudgetLoop activity mark and a concise current-state label instead of a generic spinner-only state

#### Scenario: Reduced motion is preferred
- **WHEN** the operating system reports `prefers-reduced-motion: reduce`
- **THEN** orbit and morph movement stop while a non-motion visual and text status remain available
