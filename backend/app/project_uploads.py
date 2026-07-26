"""Bounded browser-folder snapshots used only to seed isolated workspaces."""
from __future__ import annotations

import shutil
import uuid
from pathlib import Path, PurePosixPath

from fastapi import UploadFile

from app.core.config import settings

UPLOAD_CHUNK_BYTES = 1024 * 1024
FORBIDDEN_PARTS = frozenset({".git", ".budgetloop"})
IGNORED_NAMES = frozenset({".DS_Store"})


class ProjectUploadError(ValueError):
    """A browser project snapshot is invalid or exceeds a configured bound."""


def project_upload_root() -> Path:
    root = Path(settings.artifact_local_dir).expanduser().resolve() / "project-uploads"
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    return root


def _relative_paths(raw_paths: list[str]) -> list[PurePosixPath | None]:
    if not raw_paths:
        raise ProjectUploadError("project folder contains no files")
    parsed: list[PurePosixPath | None] = []
    usable: list[PurePosixPath] = []
    for raw in raw_paths:
        value = raw.replace("\\", "/").strip()
        path = PurePosixPath(value)
        if (
            not value
            or path.is_absolute()
            or any(part in {"", ".", ".."} for part in path.parts)
        ):
            raise ProjectUploadError(f"invalid project relative path: {raw!r}")
        if any(part in FORBIDDEN_PARTS for part in path.parts):
            raise ProjectUploadError(f"project metadata path is not uploadable: {raw!r}")
        if path.name in IGNORED_NAMES:
            parsed.append(None)
            continue
        parsed.append(path)
        usable.append(path)

    if not usable:
        raise ProjectUploadError("project folder contains no usable files")
    common_root = usable[0].parts[0]
    strip_root = all(len(path.parts) > 1 and path.parts[0] == common_root for path in usable)
    normalized: list[PurePosixPath | None] = []
    seen: set[str] = set()
    for path in parsed:
        if path is None:
            normalized.append(None)
            continue
        selected = PurePosixPath(*path.parts[1:]) if strip_root else path
        key = selected.as_posix()
        if key in seen:
            raise ProjectUploadError(f"duplicate project relative path: {key!r}")
        seen.add(key)
        normalized.append(selected)
    return normalized


async def store_project_upload(files: list[UploadFile], paths: list[str]) -> dict[str, int | str]:
    if len(files) != len(paths):
        raise ProjectUploadError("each uploaded file requires one relative path")
    if len(files) > settings.project_upload_max_files:
        raise ProjectUploadError(
            f"project folder exceeds {settings.project_upload_max_files} files"
        )
    normalized = _relative_paths(paths)
    upload_id = uuid.uuid4()
    root = project_upload_root()
    staging = root / f".{upload_id}.tmp"
    destination = root / str(upload_id)
    staging.mkdir(mode=0o700)
    total_bytes = 0
    stored_files = 0
    try:
        for upload, relative in zip(files, normalized, strict=True):
            if relative is None:
                await upload.close()
                continue
            target = (staging / Path(*relative.parts)).resolve()
            if staging not in target.parents:
                raise ProjectUploadError(f"project path escapes upload root: {relative}")
            target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            file_bytes = 0
            with target.open("xb") as output:
                while chunk := await upload.read(UPLOAD_CHUNK_BYTES):
                    file_bytes += len(chunk)
                    total_bytes += len(chunk)
                    if file_bytes > settings.project_upload_max_file_bytes:
                        raise ProjectUploadError(
                            f"file exceeds {settings.project_upload_max_file_bytes} bytes: {relative}"
                        )
                    if total_bytes > settings.project_upload_max_total_bytes:
                        raise ProjectUploadError(
                            f"project folder exceeds {settings.project_upload_max_total_bytes} bytes"
                        )
                    output.write(chunk)
            await upload.close()
            stored_files += 1
        staging.rename(destination)
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    return {
        "upload_id": str(upload_id),
        "file_count": stored_files,
        "total_bytes": total_bytes,
    }


def resolve_project_upload(upload_id: str | uuid.UUID) -> Path:
    try:
        safe_id = uuid.UUID(str(upload_id))
    except ValueError as exc:
        raise ProjectUploadError("invalid project upload identifier") from exc
    root = project_upload_root()
    candidate = (root / str(safe_id)).resolve()
    if root not in candidate.parents or not candidate.is_dir():
        raise ProjectUploadError("project upload snapshot is missing")
    return candidate
