## ADDED Requirements

### Requirement: Shared visual system
The frontend SHALL use shared tokens and reusable primitives for typography, spacing, color, surfaces, controls, status, feedback, and motion across all primary routes.

#### Scenario: Repeated component appears on different routes
- **WHEN** the same semantic control, status, field, or feedback pattern is rendered on multiple routes
- **THEN** it uses the same component family and only documented variants create visual differences

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
