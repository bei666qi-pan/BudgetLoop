## MODIFIED Requirements

### Requirement: Full-access team worktree isolation
Every enabled session in a full-access preset team SHALL operate in a unique server-generated Git worktree derived from its session identifier and SHALL never execute concurrently in the selected repository root. A full-access team SHALL select a server execution engine that can mount the confirmed host project.

#### Scenario: Full-access sessions provision successfully
- **WHEN** confirmed team runs provision the writable host project through the supported server execution engine
- **THEN** each session receives a unique branch and worktree below the controlled workspace location and its Agent conversation starts in that worktree

#### Scenario: Worktree cannot be honored
- **WHEN** mount, Git initialization, branch creation, or worktree validation fails for a requested full-access session
- **THEN** that run fails visibly with an actionable workspace error and does not fall back to a shared folder or isolated copy
