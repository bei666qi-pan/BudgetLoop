## ADDED Requirements

### Requirement: Server-side credential boundary
The production web deployment SHALL keep the control-plane token and upstream AI key in server-side configuration, SHALL route browser API and event traffic through a same-origin server handler, and SHALL NOT embed either credential in browser bundles, responses or logs.

#### Scenario: Browser calls the control plane
- **WHEN** a production browser requests an allowed BudgetLoop API or event path
- **THEN** the Next.js server forwards it to the configured control plane with server-side authorization while the browser request and delivered JavaScript contain no secret token

#### Scenario: Browser attempts to use the proxy generically
- **WHEN** a request names a non-BudgetLoop path, unsupported method or oversized body
- **THEN** the server handler rejects it without forwarding and without reflecting configured credentials

### Requirement: Reproducible domestic deployment
The project SHALL provide a production deployment definition that builds the web and control-plane services from their repository folders, uses domestic-reachable image/package sources, provisions required persistence and worker connectivity, and supports GitHub source, Gitee mirror and Coolify rollout.

#### Scenario: Coolify builds the mirrored revision
- **WHEN** Coolify deploys the Gitee `master` revision with required server variables
- **THEN** it builds the web and backend services, starts Postgres, Valkey, control-plane and worker dependencies, and exposes only the web origin at the configured public domain

### Requirement: Verified production readiness
A production rollout SHALL NOT be reported complete until the deployment has finished, required services are healthy, the public homepage and same-origin health route respond successfully, and the configured compatible AI model completes a bounded draft-generation smoke test.

#### Scenario: A service is unhealthy or AI authentication fails
- **WHEN** Coolify finishes a build but any required readiness or AI smoke check fails
- **THEN** the rollout is reported as failed or incomplete with the failing layer identified rather than being declared deployed
