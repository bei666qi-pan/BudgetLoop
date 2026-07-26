## 1. Creation contract and budget semantics

- [x] 1.1 Add guided/autonomous and bounded/Max request, snapshot, and frontend type contracts with backwards-compatible defaults.
- [x] 1.2 Implement Max-mode run creation, budget reservation, pressure, phase, and loop behavior while preserving accounting.
- [x] 1.3 Add focused backend unit tests for bounded versus Max budget behavior.

## 2. Autonomous staged coordination

- [x] 2.1 Add an idempotent autonomous stage coordinator that records public-output handoffs and releases eligible parallel stages.
- [x] 2.2 Integrate autonomous role guidance and completion-triggered coordination with the worker and preset start path.
- [x] 2.3 Add API/coordinator tests for staged dispatch, successful handoff, and failed-predecessor blocking.

## 3. Agent Team setup and presentation

- [x] 3.1 Add mode and Max budget controls plus clear safety disclosure to the Agent Team creation view.
- [x] 3.2 Show Max status accurately in team/session budget presentation without changing bounded displays.
- [x] 3.3 Add frontend tests for the request choices and Max display.

## 4. Verification

- [x] 4.1 Run relevant backend pytest suites and frontend Vitest suites.
- [x] 4.2 Run frontend production build and OpenSpec validation.
