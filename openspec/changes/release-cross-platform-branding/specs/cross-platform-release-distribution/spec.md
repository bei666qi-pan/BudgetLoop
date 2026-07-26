## ADDED Requirements

### Requirement: Traceable cross-platform release
BudgetLoop SHALL publish each cross-platform release from one immutable Git tag and SHALL make the source version, Windows MSI, macOS archive, checksums, prerequisites, and validation evidence discoverable from its GitHub Release.

#### Scenario: Operator downloads a release
- **WHEN** an operator opens a published BudgetLoop GitHub Release
- **THEN** the release identifies its tag and source revision, provides the Windows MSI and macOS archive, and states Docker Desktop and platform prerequisites without claiming that installers contain Docker or provider credentials

#### Scenario: Release assets are built
- **WHEN** the Windows MSI and macOS archive are prepared for a tag
- **THEN** each artifact reports the tagged version, has a recorded SHA-256 checksum, and originates from the tagged source revision

#### Scenario: A release gate fails
- **WHEN** required web, macOS, or Windows validation does not pass
- **THEN** the affected artifact is not represented as a verified current release asset and the failed gate is reported
