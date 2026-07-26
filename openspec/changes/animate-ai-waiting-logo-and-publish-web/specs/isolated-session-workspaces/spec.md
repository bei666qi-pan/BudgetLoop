## ADDED Requirements

### Requirement: Uploaded snapshot workspace initialization
An isolated run SHALL be initializable from an opaque, validated browser upload snapshot, SHALL copy that snapshot into its own workspace before the Git baseline is created, and SHALL NOT translate the upload into a host-folder mount or broader access mode.

#### Scenario: Agent Team starts from an uploaded project
- **WHEN** an isolated Agent Team is created with a valid project upload identifier
- **THEN** every session receives an independent workspace copy of the same uploaded files before work begins

#### Scenario: Upload snapshot is missing or invalid at provisioning
- **WHEN** a recorded upload identifier cannot be resolved to a valid snapshot below the configured upload root
- **THEN** workspace provisioning fails visibly and does not continue with an empty workspace or full-access fallback

#### Scenario: Upload identifier is combined with direct access
- **WHEN** task creation combines a project upload identifier with full-access mode or a host project directory
- **THEN** the API rejects the request and creates no team or run
