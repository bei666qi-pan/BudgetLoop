## MODIFIED Requirements

### Requirement: Traceable cross-platform release
BudgetLoop SHALL publish each cross-platform release from one immutable Git tag; SHALL keep the canonical release version synchronized across the Web package, backend package, macOS bundle, Windows package, Tauri bundle, Rust crate, and release documentation; and SHALL make the source version, Windows MSI, macOS archive, checksums, prerequisites, and validation evidence discoverable from its GitHub Release.

#### Scenario: Operator downloads a release
- **WHEN** an operator opens a published BudgetLoop GitHub Release
- **THEN** the release identifies its tag and source revision, provides the Windows MSI and macOS archive, links to separate English and Chinese documentation, and states Docker Desktop and platform prerequisites without claiming that installers contain Docker or provider credentials

#### Scenario: Release assets are built
- **WHEN** the Windows MSI and macOS archive are prepared for a tag
- **THEN** each artifact reports the tagged version, has a recorded SHA-256 checksum, originates from the tagged source revision, and is published only after the Web, backend, version-parity, and native-platform gates pass

#### Scenario: A release gate fails
- **WHEN** required Web, backend, version-parity, macOS, or Windows validation does not pass
- **THEN** the affected artifact is not represented as a verified current release asset and the failed gate is reported

#### Scenario: Operator reads repository documentation
- **WHEN** an operator opens the repository landing page
- **THEN** English is shown first, a visible language selector opens the complete Chinese document, and both documents report the same current version, platform status, prerequisites, and release links
