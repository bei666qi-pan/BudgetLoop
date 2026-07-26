## 1. Accounting implementation

- [x] 1.1 Track managed-runtime accounting mode from the workspace handle for both new and resumed agent-server conversations.
- [x] 1.2 Release the outer iteration reservation after managed observation without duplicating proxy-settled usage; preserve non-managed settlement and error release.
- [x] 1.3 Show terminal phase copy for completed runs instead of the pre-start fallback.

## 2. Verification

- [x] 2.1 Add focused orchestrator regression tests for managed release-only and non-managed settlement behavior.
- [x] 2.2 Add focused frontend coverage for terminal phase copy and run backend/frontend tests plus strict OpenSpec validation.
- [x] 2.3 Rebuild stateless services and verify a real managed run's budget totals match its persisted LLM observations with zero reservations.
