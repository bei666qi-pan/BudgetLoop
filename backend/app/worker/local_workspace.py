"""Persistent, per-run local workspaces for CLI execution engines.

The control plane owns the directory and git lifecycle. Engines receive only the
resolved run/worktree directory; they never choose or reuse another run's path.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import uuid
from pathlib import Path

from app.ai_runtime import managed_runtime_environment
from app.core.config import settings
from app.worker.workspace_manager import WorkspaceError, WorkspaceHandle


class LocalWorkspaceManager:
    """Provision an isolated persistent repository below a configured root."""

    def __init__(self, root: str | Path | None = None):
        self.root = Path(root or settings.cli_workspace_root).expanduser().resolve()
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)

    def provision(
        self,
        run_id: str,
        *,
        source_dir: str | Path | None = None,
        working_dir: str = "/workspace",
        worktree_session_id: str | None = None,
        folder_access: str = "isolated",
        project_dir: str | Path | None = None,
    ) -> WorkspaceHandle:
        del working_dir, project_dir
        if folder_access != "isolated":
            # 本地工作区无法 bind-mount 宿主目录；fail-closed，绝不静默回退为隔离
            raise WorkspaceError(
                f"local workspace cannot honor folder_access={folder_access!r}: "
                "host-folder mounts are only supported by the docker workspace"
            )
        safe_run_id = uuid.UUID(str(run_id)).hex
        run_root = self.root / safe_run_id
        repository = run_root / "repository"
        if repository.exists():
            return self.attach(
                run_id,
                f"local:{safe_run_id}",
                worktree_branch=None,
            )

        run_root.mkdir(parents=True, exist_ok=True, mode=0o700)
        source = Path(source_dir).expanduser().resolve() if source_dir else None
        if source is not None and source.is_dir():
            self._validate_source_symlinks(source)
            shutil.copytree(
                source,
                repository,
                symlinks=True,
                ignore=shutil.ignore_patterns(".budgetloop"),
            )
        else:
            repository.mkdir(mode=0o700)
        self._ensure_git_repository(repository)

        selected = repository
        branch = None
        worktree_path = None
        if worktree_session_id is not None:
            branch, selected = self._create_worktree(repository, worktree_session_id)
            worktree_path = str(selected)
        return self._handle(
            safe_run_id,
            selected,
            worktree_branch=branch,
            worktree_path=worktree_path,
        )

    def attach(
        self,
        run_id: str,
        workspace_id: str,
        *,
        working_dir: str = "/workspace",
        worktree_branch: str | None = None,
    ) -> WorkspaceHandle:
        safe_run_id = uuid.UUID(str(run_id)).hex
        expected_id = f"local:{safe_run_id}"
        if workspace_id != expected_id:
            raise WorkspaceError("local workspace id does not belong to this run")
        repository = self.root / safe_run_id / "repository"
        if not repository.is_dir():
            raise WorkspaceError(f"local workspace not found: {expected_id}")
        selected = repository
        worktree_path = None
        if worktree_branch:
            candidate = Path(working_dir).expanduser().resolve()
            run_root = self.root / safe_run_id
            if candidate == Path("/workspace") or run_root not in candidate.parents:
                raise WorkspaceError("local worktree path does not belong to this run")
            if not candidate.is_dir():
                raise WorkspaceError(f"local worktree not found: {worktree_branch}")
            selected = candidate
            worktree_path = str(candidate)
        return self._handle(
            safe_run_id,
            selected,
            worktree_branch=worktree_branch,
            worktree_path=worktree_path,
        )

    def destroy(self, run_id: str) -> None:
        """Retain the workspace for audit, handoff and crash recovery."""
        uuid.UUID(str(run_id))

    @staticmethod
    def _validate_source_symlinks(source: Path) -> None:
        source_prefix = f"{source}{os.sep}"
        for path in source.rglob("*"):
            if not path.is_symlink():
                continue
            resolved = path.resolve()
            if resolved != source and not str(resolved).startswith(source_prefix):
                raise WorkspaceError(f"source contains an external symlink: {path}")

    @staticmethod
    def _run_git(repository: Path, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["git", "-C", str(repository), *args],
            check=False,
            capture_output=True,
            text=True,
            timeout=60,
        )

    def _ensure_git_repository(self, repository: Path) -> None:
        inside = self._run_git(repository, "rev-parse", "--is-inside-work-tree")
        if inside.returncode != 0:
            initialized = self._run_git(repository, "init", "-q")
            if initialized.returncode != 0:
                raise WorkspaceError(f"git init failed: {initialized.stderr[:500]}")
        self._run_git(repository, "config", "user.email", "budgetloop@local")
        self._run_git(repository, "config", "user.name", "BudgetLoop")
        self._run_git(repository, "add", "-A")
        committed = self._run_git(repository, "commit", "-q", "-m", "init", "--allow-empty")
        if committed.returncode != 0:
            raise WorkspaceError(f"initial commit failed: {committed.stderr[:500]}")

    def _create_worktree(self, repository: Path, session_id: str) -> tuple[str, Path]:
        safe_session_id = uuid.UUID(str(session_id)).hex
        branch = f"bl/session-{safe_session_id[:12]}"
        target = repository.parent / "worktrees" / safe_session_id
        target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        result = self._run_git(repository, "worktree", "add", "-b", branch, str(target), "HEAD")
        if result.returncode != 0:
            raise WorkspaceError(f"git worktree setup failed: {result.stderr[:500]}")
        return branch, target

    @staticmethod
    def _handle(
        safe_run_id: str,
        working_dir: Path,
        *,
        worktree_branch: str | None,
        worktree_path: str | None,
    ) -> WorkspaceHandle:
        return WorkspaceHandle(
            container_id=f"local:{safe_run_id}",
            base_url=f"local://{safe_run_id}",
            session_key="",
            volume_name=f"budgetloop-local-{safe_run_id}",
            working_dir=str(working_dir),
            worktree_branch=worktree_branch,
            worktree_path=worktree_path,
            runtime_env=managed_runtime_environment(uuid.UUID(safe_run_id)),
        )
