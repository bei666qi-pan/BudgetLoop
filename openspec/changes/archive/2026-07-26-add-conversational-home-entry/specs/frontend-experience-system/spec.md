## ADDED Requirements

### Requirement: Accessible conversational intake
The frontend SHALL implement the home composer, planning feedback, clarification, and draft review with semantic forms, keyboard operation, visible focus, accessible names, announced state changes, and reduced-motion behavior from the shared design system.

#### Scenario: Keyboard-only operator creates a draft
- **WHEN** the operator enters and submits a goal using only the keyboard
- **THEN** focus moves predictably to planning feedback or the resulting draft and all review/edit/confirmation actions remain keyboard reachable

#### Scenario: Planning state changes
- **WHEN** draft generation moves between planning, needs-input, ready, or error
- **THEN** a concise status is announced without moving focus unexpectedly or relying on color alone

### Requirement: Responsive setup review
The composer and setup review SHALL remain usable at approximately 390 CSS pixels and desktop widths without horizontal page overflow, hidden permissions, or unreachable confirmation actions.

#### Scenario: Draft is reviewed on a narrow viewport
- **WHEN** a ready draft is displayed on a narrow screen
- **THEN** review groups reflow into a readable order and the effective budget, folder mode, risk acknowledgement, and final action remain reachable without covering editable content

### Requirement: Trustworthy AI and authorization presentation
The frontend SHALL visually and semantically distinguish AI-suggested configuration, deterministic fallback, operator-controlled permissions, server validation, and actual creation state.

#### Scenario: Local fallback is used
- **WHEN** the draft response reports local fallback provenance
- **THEN** the interface labels the recommendation source and still presents the valid draft without claiming AI participation

#### Scenario: Writable access is not confirmed
- **WHEN** a suggested task is ready but full-access acknowledgement is missing
- **THEN** the interface does not present the setup as authorized or started and explains the exact remaining operator action

#### Scenario: Confirmation fails
- **WHEN** preset team creation returns an error
- **THEN** the draft, permission selection, and recoverable edits remain visible, the error identifies the failed action, and no success or navigation state is fabricated

