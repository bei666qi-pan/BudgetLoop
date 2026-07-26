# frontend-experience-system Specification

## Purpose

Define the shared visual, responsive, accessible, and trustworthy interaction foundation for BudgetLoop's primary frontend workflows.

## Requirements

### Requirement: Shared visual system
The frontend SHALL use shared tokens and reusable primitives for typography, spacing, color, surfaces, controls, status, feedback, and motion across all primary routes. Each recurring pattern (tables, tab bars, progress bars, status badges, banners) SHALL have exactly one canonical implementation that routes reuse, color values SHALL come from the design-token palette rather than ad-hoc hex or raw palette utilities, and the committed design-system document SHALL describe the theme the application actually ships.

#### Scenario: Repeated component appears on different routes
- **WHEN** the same semantic control, status, field, or feedback pattern is rendered on multiple routes
- **THEN** it uses the same component family and only documented variants create visual differences

#### Scenario: Color is applied to a surface, chart, or control
- **WHEN** a component applies color to any surface, chart series, border, or control
- **THEN** the value resolves to a semantic design token from the shared palette, not a one-off hex code or raw default-palette utility

#### Scenario: Design-system documentation is consulted
- **WHEN** a contributor reads the committed design-system document
- **THEN** the colors, surfaces, radii, and typography it describes match the theme the application renders

#### Scenario: Unused primitives accumulate
- **WHEN** a primitive or component is no longer imported by any route
- **THEN** it is removed from the codebase rather than left to compete with the canonical implementation

### Requirement: Responsive primary workflows
The dashboard, creation flow, run command center, approval interaction, and report SHALL remain usable at mobile and desktop widths without horizontal page overflow or clipped primary actions.

#### Scenario: Operator uses a narrow viewport
- **WHEN** the viewport is approximately 390 CSS pixels wide
- **THEN** primary content reflows into a readable order, tap targets remain usable, and wide diagnostics use contained scrolling or an equivalent accessible treatment

### Requirement: Accessible interaction
Interactive elements SHALL be keyboard reachable, display visible focus, expose accessible names and relevant state, use semantic HTML, and avoid color-only communication. Motion SHALL respect `prefers-reduced-motion`.

#### Scenario: Keyboard-only operation
- **WHEN** an operator navigates the primary workflow using the keyboard
- **THEN** focus order follows the visual hierarchy and all required actions can be completed with visible focus

#### Scenario: Reduced motion is requested
- **WHEN** the user agent reports `prefers-reduced-motion: reduce`
- **THEN** non-essential animation and transitions are disabled or reduced to effectively immediate changes

### Requirement: Trustworthy feedback
The frontend SHALL clearly distinguish loading, empty, success, warning, terminal failure, API failure, and partial-data states and SHALL not present speculative or simulated backend facts as real.

#### Scenario: Backend error is shown
- **WHEN** an API action fails
- **THEN** the message identifies the failed action in plain language, preserves recoverable user input or known data, and offers retry when safe

### Requirement: Readable operational typography
Content, controls, tables, charts, code, and metadata SHALL use intentional type sizes and line heights that remain readable at supported breakpoints; browser-default control typography SHALL not determine the interface hierarchy.

#### Scenario: Dense diagnostic content is rendered
- **WHEN** tables, event details, code summaries, or budget metadata are displayed
- **THEN** labels and values remain legible and distinguishable without shrinking essential content below the system's minimum readable scale

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

### Requirement: Branded AI waiting feedback
All conversational AI planning and task-creation waiting states SHALL reuse one code-rendered activity component based on the interlocking-loop BudgetLoop mark, with distinct but restrained geometric disturbance, accessible status text and a recognizable static reduced-motion state.

#### Scenario: AI planning is in progress
- **WHEN** the conversational flow is waiting for an AI planning response
- **THEN** the full-size double-loop mark animates through bounded deformation while a concise live status is available to assistive technology

#### Scenario: An inline action is pending
- **WHEN** a compact button is waiting for AI planning or task creation
- **THEN** the same double-loop mark appears in its compact variant without changing the button's accessible name

#### Scenario: Reduced motion is preferred
- **WHEN** the user agent requests reduced motion
- **THEN** the disturbance and ambient motion stop and the undistorted double-loop mark remains visible with the same status text
