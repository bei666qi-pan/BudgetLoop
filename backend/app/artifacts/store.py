"""Store large artifacts outside PostgreSQL while keeping stable references."""

from __future__ import annotations

import io
from abc import ABC, abstractmethod
from pathlib import Path

from app.core.config import settings


class ArtifactNotFound(Exception):
    """The requested artifact reference does not exist."""


class ArtifactStore(ABC):
    """Storage contract for complete logs, diffs, and report bodies."""

    @abstractmethod
    def put_bytes(self, key: str, data: bytes) -> str:
        """Write data under key and return its stable reference."""

    @abstractmethod
    def get_bytes(self, ref: str) -> bytes:
        """Read data by reference or raise ArtifactNotFound."""


class LocalVolumeArtifactStore(ArtifactStore):
    """Store relative keys in a local volume without permitting traversal."""

    def __init__(self, root: str | Path | None = None):
        self.root = Path(root or settings.artifact_local_dir).resolve()

    def _resolve(self, key: str) -> Path:
        path = (self.root / key).resolve()
        if path != self.root and self.root not in path.parents:
            raise ValueError(f"artifact key escapes store root: {key!r}")
        return path

    def put_bytes(self, key: str, data: bytes) -> str:
        path = self._resolve(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return key

    def get_bytes(self, ref: str) -> bytes:
        path = self._resolve(ref)
        if not path.is_file():
            raise ArtifactNotFound(f"artifact not found: {ref!r}")
        return path.read_bytes()


class MinioArtifactStore(ArtifactStore):
    """Store artifacts in the configured MinIO/S3-compatible bucket."""

    def __init__(self) -> None:
        try:
            from minio import Minio  # noqa: PLC0415
            from minio.error import S3Error  # noqa: PLC0415
        except ImportError as exc:  # pragma: no cover - depends on optional installation
            raise RuntimeError(
                "artifact_backend=minio requires the minio package: pip install 'minio>=7.2'"
            ) from exc
        self._s3_error = S3Error
        self.bucket = settings.minio_bucket
        self.client = Minio(
            settings.minio_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=settings.minio_endpoint.startswith("https"),
        )
        if not self.client.bucket_exists(self.bucket):
            self.client.make_bucket(self.bucket)

    def put_bytes(self, key: str, data: bytes) -> str:
        self.client.put_object(self.bucket, key, io.BytesIO(data), length=len(data))
        return key

    def get_bytes(self, ref: str) -> bytes:
        try:
            response = self.client.get_object(self.bucket, ref)
            try:
                return response.read()
            finally:
                response.close()
                response.release_conn()
        except self._s3_error as exc:
            if exc.code in ("NoSuchKey", "NoSuchObject"):
                raise ArtifactNotFound(f"artifact not found: {ref!r}") from exc
            raise


_store: ArtifactStore | None = None


def get_store() -> ArtifactStore:
    """Return the configured process-local artifact store singleton."""
    global _store
    if _store is None:
        backend = settings.artifact_backend
        if backend == "local":
            _store = LocalVolumeArtifactStore()
        elif backend == "minio":
            _store = MinioArtifactStore()
        else:
            raise ValueError(f"unknown artifact_backend: {backend!r} (expected local|minio)")
    return _store
