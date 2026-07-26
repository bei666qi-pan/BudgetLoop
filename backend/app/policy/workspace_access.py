"""Codex-derived host-folder access policy shared by every creation API.

The policy is declarative (`folder_access` + canonical `project_dir`). Docker
workspace provisioning remains the only enforcer. Keeping normalization here
prevents single-task and Agent Team creation from accepting different roots.
"""
from __future__ import annotations

import os
from pathlib import PurePosixPath
from typing import Literal

FolderAccess = Literal["isolated", "full_access"]

SENSITIVE_PROJECT_ROOTS = (
    "/System",
    "/usr",
    "/bin",
    "/etc",
    "/var",
    "/private",
    "/Applications",
    "/Library",
)


def normalize_project_dir(value: str | None) -> str | None:
    """Return a canonical allowed POSIX project root, or ``None`` for blank input."""
    if value is None:
        return None
    value = value.strip()
    if not value:
        return None
    path = PurePosixPath(value)
    if not path.is_absolute() or ".." in path.parts:
        raise ValueError("project_dir must be an absolute normalized POSIX path")
    normalized = str(path)
    if normalized.startswith("//"):
        normalized = "/" + normalized.lstrip("/")
    if normalized == "/":
        raise ValueError("project_dir must not be the filesystem root")
    if normalized == str(PurePosixPath(os.path.expanduser("~"))):
        raise ValueError("project_dir must not be the user's home directory")
    for root in SENSITIVE_PROJECT_ROOTS:
        if normalized == root or normalized.startswith(f"{root}/"):
            raise ValueError(f"project_dir is not allowed under system location: {root}")
    return normalized


def validate_workspace_access(folder_access: FolderAccess, project_dir: str | None) -> None:
    """Validate cross-field invariants without broadening or silently downgrading access."""
    if folder_access == "full_access" and not project_dir:
        raise ValueError("project_dir is required when folder_access is full_access")
