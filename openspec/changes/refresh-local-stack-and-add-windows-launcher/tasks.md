## 1. Fresh local application stack

- [x] 1.1 Replace the hard-coded unavailable Node mirror default with the portable official image while preserving an explicit override.
- [x] 1.2 Refresh only `control-plane`, `worker`, and `web` before macOS adopts a healthy stack, with redacted failure handling and no data-service teardown.
- [x] 1.3 Build the macOS launcher and rebuild the local Compose application services from current source.

## 2. Windows native launcher

- [x] 2.1 Add the Tauri v2 Windows host, native repository selection/persistence, Docker Compose invocation, health gating, and visible failures.
- [x] 2.2 Add unit tests for safe repository resolution and the restricted stateless Compose command.
- [x] 2.3 Add Windows launcher documentation and package metadata without embedding credentials.

## 3. Windows release pipeline and acceptance

- [x] 3.1 Add a Windows GitHub Actions workflow that runs launcher tests, builds an MSI, and uploads the artifact without publishing on failure.
- [x] 3.2 Run source-level checks, strict OpenSpec validation, actual local browser interaction acceptance for autonomous mode and Max, and inspect runtime health/logs.
- [ ] 3.3 Push the scoped change, wait for the Windows workflow, inspect its MSI artifact, and publish the GitHub release only after all gates pass.
