## MODIFIED Requirements

### Requirement: Health gating with readable failures
The app SHALL refresh the stateless `control-plane`, `worker`, and `web`
Compose services with a cached `docker compose up -d --build` invocation before
adopting or presenting a local stack. It SHALL preserve PostgreSQL, Valkey,
New API, volumes, and an existing `.env`; it SHALL gate window presentation on
the control-plane, gateway, and web health checks, and SHALL present failures
as readable states that name the failed step and a concrete remedy.

#### Scenario: Port conflict
- **WHEN** a required port is already bound by an unhealthy or foreign process
- **THEN** the app reports which port conflicts and how to free it, without crashing

#### Scenario: Healthy stack already running
- **WHEN** the control-plane and web endpoints already answer health checks before the app starts anything
- **THEN** the app rebuilds and refreshes only the stateless application services, waits for health, and opens the window without restarting data services

#### Scenario: Stateless refresh fails
- **WHEN** rebuilding or recreating a stateless application service fails
- **THEN** the app does not present the web UI and reports a redacted failure plus a concrete Docker recovery action
