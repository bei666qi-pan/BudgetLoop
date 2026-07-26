## MODIFIED Requirements

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
