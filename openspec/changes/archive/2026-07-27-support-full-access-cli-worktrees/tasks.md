## 1. Full-access engine compatibility

- [x] 1.1 Reject full-access Agent Team requests that select a CLI execution engine before creating any runs.
- [x] 1.2 Preserve CLI execution for isolated workspaces and use OpenHands for direct project access.

## 2. Regression coverage

- [x] 2.1 Make the guided setup switch to OpenHands and hide CLI choices when direct project access is selected.
- [x] 2.2 Add focused API and UI regression tests for the incompatible engine combination.

## 3. Verification

- [x] 3.1 Run the frontend test/build suite, verify the deployed API rejection, and validate the OpenSpec change.
