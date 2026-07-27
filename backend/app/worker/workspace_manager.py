"""WorkspaceManager：每个运行中的 task_run 一个独立 Workspace 容器（agent-server 镜像）。

- provision(run_id)：起容器 + 命名卷（budgetloop-ws-<run_id>，保留以便崩溃恢复）
  + 拷贝 fixture 进容器 working_dir + 容器内 git init / 初始 commit；
  folder_access=full_access 时改为把宿主 project_dir 以 rw 挂载到 working_dir
  （跳过命名卷与 fixture 拷贝；已有 .git 时不重新 init；挂载失败 fail-closed）；
- attach(run_id, container_id)：崩溃恢复时重连已有容器；
- destroy(run_id)：停止并删除容器（保留卷）。

docker daemon 不可达等底层异常统一包装为 WorkspaceError。
"""
from __future__ import annotations

import io
import secrets
import shlex
import tarfile
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path

import docker
import docker.errors
import httpx

from app.ai_runtime import managed_runtime_environment
from app.core.config import settings

# 容器内 agent-server 监听端口与工作目录
AGENT_SERVER_PORT = 8000
CONTAINER_WORKDIR = "/workspace"

LABEL_RUN_ID = "budgetloop.run_id"
HEALTH_TIMEOUT_SECONDS = 120.0


class WorkspaceError(Exception):
    """workspace 容器操作失败（含 docker daemon 不可达）。"""


@dataclass(frozen=True)
class WorkspaceHandle:
    container_id: str
    base_url: str
    session_key: str
    volume_name: str
    working_dir: str = CONTAINER_WORKDIR
    worktree_branch: str | None = None
    worktree_path: str | None = None
    runtime_env: dict[str, str] = field(default_factory=dict)


class WorkspaceManager:
    def __init__(self, docker_client=None, image: str | None = None):
        self.image = image or settings.agent_server_image
        if docker_client is not None:
            self._docker = docker_client
        else:
            try:
                self._docker = docker.from_env()
                self._docker.ping()
            except docker.errors.DockerException as exc:
                raise WorkspaceError(f"docker daemon unreachable: {exc}") from exc

    # ------------------------------------------------------------------
    def provision(
        self,
        run_id: str,
        *,
        source_dir: str | Path | None = None,
        working_dir: str = CONTAINER_WORKDIR,
        worktree_session_id: str | None = None,
        folder_access: str = "isolated",
        project_dir: str | Path | None = None,
    ) -> WorkspaceHandle:
        """起一个新 workspace 容器并等待 /health 就绪。

        folder_access=full_access 时把宿主 project_dir 以 rw 直接挂载到 working_dir
        （替代命名卷，跳过 fixture 拷贝）；docker 拒绝挂载则 fail-closed 报错，
        绝不静默回退到隔离卷。
        """
        session_key = secrets.token_urlsafe(32)
        runtime_env = managed_runtime_environment(run_id, container=True)
        volume_name = f"budgetloop-ws-{run_id}"
        full_access = folder_access == "full_access"
        if full_access and project_dir is None:
            raise WorkspaceError("full_access mode requires a project_dir to mount")
        try:
            if full_access:
                volumes = {str(project_dir): {"bind": working_dir, "mode": "rw"}}
            else:
                volume = self._ensure_volume(volume_name)
                volumes = {volume.name: {"bind": working_dir, "mode": "rw"}}
            container = self._docker.containers.run(
                self.image,
                detach=True,
                environment={
                    "OH_SESSION_API_KEYS_0": session_key,
                    "OH_ALLOW_CORS_ORIGINS_0": "*",
                    **runtime_env,
                },
                volumes=volumes,
                ports={f"{AGENT_SERVER_PORT}/tcp": None},  # 随机主机端口
                labels={LABEL_RUN_ID: str(run_id)},
            )
        except docker.errors.DockerException as exc:
            if full_access:
                raise WorkspaceError(
                    f"failed to mount project folder {project_dir} at {working_dir}: {exc}"
                ) from exc
            raise WorkspaceError(f"failed to start workspace container: {exc}") from exc

        try:
            base_url = self._base_url(container)
            self._wait_healthy(base_url, session_key)
            if full_access:
                # 挂载的宿主文件夹即项目本身；仅在缺少 .git 时建立 git 基线
                if not self._has_git_repo(container, working_dir):
                    self._git_init(container, working_dir)
            else:
                if source_dir is not None:
                    self._copy_fixture(container, Path(source_dir), working_dir)
                self._git_init(container, working_dir)
            branch = None
            worktree_path = None
            selected_working_dir = working_dir
            if worktree_session_id is not None:
                branch, worktree_path = self._create_worktree(
                    container, working_dir, worktree_session_id
                )
                selected_working_dir = worktree_path
        except Exception:
            self._remove_container(container)
            raise
        return WorkspaceHandle(
            container_id=container.id,
            base_url=base_url,
            session_key=session_key,
            volume_name=volume_name,
            working_dir=selected_working_dir,
            worktree_branch=branch,
            worktree_path=worktree_path,
            runtime_env=runtime_env,
        )

    def attach(
        self,
        run_id: str,
        container_id: str,
        *,
        working_dir: str = CONTAINER_WORKDIR,
        worktree_branch: str | None = None,
    ) -> WorkspaceHandle:
        """崩溃恢复：重连已有容器（容器可能已退出，尝试启动）。"""
        try:
            container = self._docker.containers.get(container_id)
            if container.status != "running":
                container.start()
            container.reload()
        except docker.errors.DockerException as exc:
            raise WorkspaceError(f"failed to attach container {container_id}: {exc}") from exc
        session_key = self._session_key_from_env(container)
        if not session_key:
            raise WorkspaceError(f"container {container_id} has no OH_SESSION_API_KEYS_0 env")
        base_url = self._base_url(container)
        self._wait_healthy(base_url, session_key)
        volume_name = f"budgetloop-ws-{run_id}"
        runtime_env = managed_runtime_environment(run_id, container=True)
        return WorkspaceHandle(
            container_id=container.id,
            base_url=base_url,
            session_key=session_key,
            volume_name=volume_name,
            working_dir=working_dir,
            worktree_branch=worktree_branch,
            worktree_path=working_dir if working_dir != CONTAINER_WORKDIR else None,
            runtime_env=runtime_env,
        )

    def destroy(self, run_id: str) -> None:
        """停止并删除容器；保留命名卷以便崩溃恢复。"""
        try:
            containers = self._docker.containers.list(all=True, filters={"label": f"{LABEL_RUN_ID}={run_id}"})
        except docker.errors.DockerException as exc:
            raise WorkspaceError(f"failed to list containers for run {run_id}: {exc}") from exc
        for container in containers:
            self._remove_container(container)

    # ------------------------------------------------------------------
    def _ensure_volume(self, name: str):
        try:
            return self._docker.volumes.get(name)
        except docker.errors.NotFound:
            return self._docker.volumes.create(name=name)
        except docker.errors.DockerException as exc:
            raise WorkspaceError(f"failed to ensure volume {name}: {exc}") from exc

    def _base_url(self, container) -> str:
        container.reload()
        ports = container.ports.get(f"{AGENT_SERVER_PORT}/tcp")
        if not ports:
            raise WorkspaceError(f"container {container.id} has no published port for {AGENT_SERVER_PORT}")
        # When the manager runs in compose's worker container, 127.0.0.1 is
        # that worker, not Docker Desktop's published-port listener. Compose
        # explicitly provides host.docker.internal; direct host-side workers
        # retain the loopback default for local development and unit tests.
        host = settings.workspace_published_host.strip() or "127.0.0.1"
        return f"http://{host}:{ports[0]['HostPort']}"

    @staticmethod
    def _session_key_from_env(container) -> str | None:
        for env in container.attrs.get("Config", {}).get("Env", []):
            if env.startswith("OH_SESSION_API_KEYS_0="):
                return env.split("=", 1)[1]
        return None

    def _wait_healthy(self, base_url: str, session_key: str) -> None:
        deadline = time.monotonic() + HEALTH_TIMEOUT_SECONDS
        last_diagnosis = "no response"
        with httpx.Client(headers={"X-Session-API-Key": session_key}, timeout=5.0) as client:
            while time.monotonic() < deadline:
                try:
                    resp = client.get(f"{base_url}/health")
                    if resp.status_code == 200:
                        return
                    last_diagnosis = f"HTTP {resp.status_code}"
                except httpx.HTTPError as exc:
                    last_diagnosis = type(exc).__name__
                time.sleep(1.0)
        raise WorkspaceError(
            "agent workspace not healthy within "
            f"{HEALTH_TIMEOUT_SECONDS:.0f}s (last health check: {last_diagnosis}); "
            "check Docker Desktop and the configured agent-server image, then retry"
        )

    @staticmethod
    def _remove_container(container) -> None:
        try:
            container.remove(force=True)
        except docker.errors.DockerException:
            pass

    def _copy_fixture(self, container, source_dir: Path, working_dir: str) -> None:
        """把宿主 fixture 目录内容拷贝进容器 working_dir。"""
        if not source_dir.is_dir():
            raise WorkspaceError(f"fixture dir not found on host: {source_dir}")
        buf = io.BytesIO()
        with tarfile.open(fileobj=buf, mode="w") as tar:
            for path in sorted(source_dir.rglob("*")):
                tar.add(path, arcname=path.relative_to(source_dir))
        buf.seek(0)
        try:
            ok = container.put_archive(working_dir, buf.read())
        except docker.errors.DockerException as exc:
            raise WorkspaceError(f"failed to copy fixture into container: {exc}") from exc
        if not ok:
            raise WorkspaceError("put_archive failed while copying fixture")

    @staticmethod
    def _has_git_repo(container, working_dir: str) -> bool:
        """容器内 working_dir 是否已有 .git（full_access 下复用既有仓库做基线）。"""
        result = container.exec_run(
            ["/bin/sh", "-c", f"test -d {shlex.quote(working_dir)}/.git"]
        )
        return result.exit_code == 0

    @staticmethod
    def _git_init(container, working_dir: str) -> None:
        """容器内 git init + 初始 commit（checkpoint/回滚的基线）。"""
        cmd = (
            f"cd {working_dir} && git init -q && "
            "git config user.email budgetloop@local && git config user.name budgetloop && "
            "git add -A && git commit -q -m init --allow-empty"
        )
        result = container.exec_run(["/bin/sh", "-c", cmd])
        if result.exit_code != 0:
            output = result.output.decode(errors="replace")[:500]
            raise WorkspaceError(f"git init failed in container: {output}")

    @staticmethod
    def _create_worktree(container, working_dir: str, session_id: str) -> tuple[str, str]:
        """Create a worktree from a server UUID only, always below the workspace root."""
        try:
            safe_id = uuid.UUID(str(session_id)).hex
        except ValueError as exc:
            raise WorkspaceError("worktree session id must be a server-generated UUID") from exc
        branch = f"bl/session-{safe_id[:12]}"
        worktree_path = f"{working_dir.rstrip('/')}/.budgetloop/worktrees/{safe_id}"
        parent = f"{working_dir.rstrip('/')}/.budgetloop/worktrees"
        command = (
            f"mkdir -p {shlex.quote(parent)} && "
            f"git -C {shlex.quote(working_dir)} worktree add "
            f"-b {shlex.quote(branch)} {shlex.quote(worktree_path)} HEAD"
        )
        result = container.exec_run(["/bin/sh", "-c", command])
        if result.exit_code != 0:
            output = result.output.decode(errors="replace")[:500]
            raise WorkspaceError(f"git worktree setup failed: {output}")
        return branch, worktree_path
