## 1. Secure conversation configuration

- [x] 1.1 Pass the provisioned workspace handle into agent conversation setup and source server-transport LLM configuration only from its managed runtime environment.
- [x] 1.2 Fail closed with a sanitized workspace error when a server workspace has no complete managed-runtime capability; retain existing CLI transport behavior.

## 2. Verification

- [x] 2.1 Add focused orchestrator tests for scoped agent-server configuration, recovery, and disabled/malformed managed-runtime paths without inspecting real secrets.
- [x] 2.2 Run focused backend tests, OpenSpec strict validation, and static checks for the changed Python modules.
- [x] 2.3 Rebuild the stateless local services and verify a real agent-server run uses the managed runtime without exposing the upstream credential.
