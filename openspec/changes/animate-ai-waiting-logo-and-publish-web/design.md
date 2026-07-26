## Context

The web waiting indicator is already centralized in `BudgetLoopActivityMark`, but its B-shaped core and orbit particles do not match the supplied interlocking-loop mark. The conversational home flow also treats native host-folder selection as the only way to provide project files: outside the macOS WKWebView bridge it tells browser users to install the app. For a public deployment, the current `NEXT_PUBLIC_API_TOKEN` pattern is also unsuitable because Next.js inlines that token into browser JavaScript.

BudgetLoop already has the pieces needed to solve these without changing its sandbox model: FastAPI/Starlette's mature `UploadFile` request handling, the configured artifact directory shared by control-plane and worker, isolated workspace seeding through `source_dir`, and Next.js route handlers as a same-origin server-side backend-for-frontend (BFF). The production stack can use the existing compatible gateway path with DeepSeek credentials injected only into the control-plane and worker environments.

## Goals / Non-Goals

**Goals:**

- Reproduce the supplied blue interlocking-loop mark as reusable SVG paths and animate it with calm, code-only geometric disturbance.
- Let a normal browser upload a bounded folder snapshot and seed every session in the resulting isolated Agent Team from that immutable snapshot.
- Preserve the macOS App's explicit direct-folder/full-access flow and make the browser distinction unambiguous.
- Remove public deployment credentials from browser bundles by routing client API and event traffic through a same-origin Next.js BFF.
- Provide a reproducible GitHub → Gitee → Coolify production deployment with domestic build mirrors, server-only DeepSeek configuration, DNS, health checks and rollback.

**Non-Goals:**

- Browser code will not obtain a real host path, write back to the user's folder, preserve symlinks, or silently request broader filesystem permission.
- Uploads are not a general artifact store, source-control replacement or cross-user collaboration feature.
- No AI gateway protocol rewrite, database schema change, sandbox-mode change or information-architecture redesign.

## Decisions

### D1: SVG symbol plus CSS transform/filter choreography

The activity component will render two stroked loop paths and a central lens matching the reference geometry. Animation is applied to lightweight SVG groups/wrappers, following Vercel's React rendering guidance, while CSS keyframes independently deform the left loop, right loop and lens using translate/scale/rotate and a restrained SVG turbulence/displacement filter. The compact variant lowers displacement and removes the ambient halo. `prefers-reduced-motion` freezes the mark in its recognizable resting form; the outer `role=status` remains the only announced node.

This keeps the asset crisp, theme-token driven and dependency-free. A GIF/video would blur at scale and cannot respect reduced motion; a canvas/WebGL effect would add unnecessary runtime and accessibility complexity.

### D2: Browser folder upload is an explicit isolated snapshot

The browser uses a hidden `input[type=file][webkitdirectory][multiple]` activated by a visible “上传项目文件夹” action. It sends a multipart request containing files and their browser-provided relative paths. The API validates an authenticated request, a maximum file count, maximum per-file and aggregate bytes, normalized relative POSIX paths, duplicate paths and forbidden metadata; absolute paths, `..`, empty names and any symlink-like entry fail closed. The server writes to a random staging directory under `ARTIFACT_LOCAL_DIR/project-uploads` using create-exclusive semantics, then atomically publishes it and returns only an opaque UUID plus a summary.

FastAPI/Starlette `UploadFile` is reused rather than introducing a custom multipart parser. The first version accepts regular files only and ignores common client-generated noise such as `.DS_Store`; binary content is allowed within the same bounds. Partial or failed uploads are removed. The API never returns server filesystem paths.

### D3: The opaque upload ID seeds isolated workspaces

Team creation accepts an optional `project_upload_id`. It is mutually exclusive with `full_access`/`project_dir`, remains bound to isolated access, and is persisted in existing run `model_config` and the container snapshot—no schema migration. Before provisioning, the worker resolves the UUID beneath the configured upload root, revalidates containment and passes that directory as the existing `source_dir`. Docker workspaces use the existing `put_archive` copy and CLI workspaces use the existing safe copy path, after which the normal Git baseline and per-session worktree logic run unchanged.

Each team session receives its own copy, so agents cannot race on a shared upload. Missing or tampered staging data fails the run visibly; it never produces an empty workspace fallback. Staged inputs are retained for the current audit lifecycle, with bounded storage as the initial operational trade-off.

### D4: Same-origin Next.js BFF for public API access

Production clients call `/api/control/...` without an operator token. A catch-all Next.js route handler forwards only allowlisted HTTP methods and paths to `CONTROL_PLANE_API_BASE`, injects `CONTROL_PLANE_API_TOKEN` server-side, strips hop-by-hop and inbound authorization headers, bounds request bodies, and streams response bodies (including server-sent events) without buffering. The browser receives sanitized backend responses but never the control-plane or DeepSeek credential.

Local development may retain the explicit `NEXT_PUBLIC_API_BASE` direct path for current workflows, but production defaults to the BFF and no longer reads `NEXT_PUBLIC_API_TOKEN`. CORS is therefore not the public trust boundary.

### D5: Coolify service deployment from the repository

The production compose file builds `web/` and `backend/` as separate images, adds Postgres and Valkey, shares the artifact volume between control-plane and worker, and mounts the Docker socket only into the worker. It omits New API because this deployment uses the existing `compatible` gateway mode against DeepSeek. Images and npm installation use domestic mirrors as required by the established deployment skill; health checks expose only application readiness.

The GitHub repository is the source of truth, Gitee `master` is the public domestic mirror, and a Coolify Docker Compose service pulls that mirror. The public domain terminates at the web service only. `API_TOKEN`, database secrets and the supplied DeepSeek key are generated/injected as server-side Coolify variables and never committed. Deployment is complete only after the Coolify rollout is finished, all required containers are healthy, the homepage and `/api/control/api/health` respond, and an authenticated AI draft smoke test reports the configured model.

## Risks / Trade-offs

- [Large or adversarial folder upload exhausts memory/disk] → stream files in chunks, enforce file/count/aggregate limits before publish, use a private staging root and remove partial uploads.
- [Relative path traversal or path collision] → normalize with `PurePosixPath`, reject absolute/dot traversal/duplicates, resolve destinations under the staging root and fail closed.
- [Team sessions observe different inputs] → publish an immutable upload directory first, then copy the same snapshot independently into each workspace.
- [BFF becomes an unintended generic proxy] → hard-code the control-plane origin, accept only `/api/...`, strip credentials/hop headers, limit methods/body size and disable caching.
- [SVG filter is expensive on low-power devices] → keep the filtered region small, animate wrappers instead of React state, reduce compact amplitude, and disable disturbance under reduced motion.
- [Coolify domestic builds stall on external registries] → use DaoCloud base-image mirrors and npmmirror; inspect deployment logs before retrying.
- [Public execution surface is demo-token authenticated rather than multi-user] → the BFF hides credentials and narrows exposure, but this release remains a single-operator deployment; multi-user identity is explicitly deferred.

## Migration Plan

1. Add the activity mark, upload/BFF contracts and targeted frontend/backend tests; verify build and suites locally.
2. Commit on a feature branch, push to GitHub, open a scoped PR, pass gates and squash-merge to `main`.
3. Mirror `main` to Gitee `master`; create or update the Coolify service and inject server-only secrets.
4. Bind `budgetloop.versecraft.cn`, deploy, poll to healthy, and run homepage, health, upload and AI-draft smoke checks.
5. Roll back by redeploying the previous Coolify commit. Uploaded snapshots are additive and can be deleted independently; existing task rows require no migration.

## Open Questions

None blocking. Multi-user authentication and automatic upload-retention cleanup are intentionally deferred beyond this single-operator deployment.
