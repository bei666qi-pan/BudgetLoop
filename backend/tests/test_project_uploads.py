from __future__ import annotations

import asyncio
import io
import os
from pathlib import Path

os.environ.setdefault("SKIP_MIGRATIONS", "1")

import pytest
from fastapi import UploadFile
from fastapi.testclient import TestClient

from app.api.team_presets import CreateTeamFromPresetRequest
from app.core.config import settings
from app.main import app
from app.project_uploads import (
    ProjectUploadError,
    resolve_project_upload,
    store_project_upload,
)


def _upload(name: str, content: bytes) -> UploadFile:
    return UploadFile(io.BytesIO(content), filename=name)


def _configure_root(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(settings, "artifact_local_dir", str(tmp_path))
    monkeypatch.setattr(settings, "project_upload_max_files", 4)
    monkeypatch.setattr(settings, "project_upload_max_file_bytes", 16)
    monkeypatch.setattr(settings, "project_upload_max_total_bytes", 24)


def test_project_upload_strips_browser_root_and_resolves_snapshot(monkeypatch, tmp_path):
    _configure_root(monkeypatch, tmp_path)
    summary = asyncio.run(
        store_project_upload(
            [_upload("main.py", b"print('ok')"), _upload("test.py", b"assert True")],
            ["demo/main.py", "demo/tests/test.py"],
        )
    )
    snapshot = resolve_project_upload(str(summary["upload_id"]))
    assert summary == {
        "upload_id": snapshot.name,
        "file_count": 2,
        "total_bytes": 22,
    }
    assert (snapshot / "main.py").read_bytes() == b"print('ok')"
    assert (snapshot / "tests/test.py").read_bytes() == b"assert True"


@pytest.mark.parametrize(
    "path",
    ["../secret", "/absolute/file", "demo/../../secret", "demo/.git/hooks/pre-commit"],
)
def test_project_upload_rejects_escaping_or_executable_metadata(
    monkeypatch, tmp_path, path
):
    _configure_root(monkeypatch, tmp_path)
    with pytest.raises(ProjectUploadError):
        asyncio.run(store_project_upload([_upload("x", b"safe")], [path]))
    assert not list((tmp_path / "project-uploads").glob(".*.tmp"))


def test_project_upload_cleans_partial_snapshot_when_size_limit_fails(monkeypatch, tmp_path):
    _configure_root(monkeypatch, tmp_path)
    with pytest.raises(ProjectUploadError, match="file exceeds"):
        asyncio.run(
            store_project_upload([_upload("large.bin", b"x" * 17)], ["demo/large.bin"])
        )
    root = tmp_path / "project-uploads"
    assert not [path for path in root.iterdir() if path.is_dir()]


def _team_request(**overrides) -> CreateTeamFromPresetRequest:
    values = {
        "preset_id": "software-delivery",
        "preset_version": 1,
        "name": "上传项目测试",
        "project_goal": "检查上传项目并补充测试",
        "shared_context": "",
        "base_workdir": "/workspace/project",
        "default_workspace_policy": "isolated",
        "role_overrides": [],
        "start_immediately": False,
        "default_execution_engine": "openhands",
        "folder_access": "isolated",
        "project_upload_id": "98ea09b8-8d59-4e8c-8ffd-e89de1529ef5",
    }
    values.update(overrides)
    return CreateTeamFromPresetRequest.model_validate(values)


def test_project_upload_identifier_is_isolated_only():
    assert str(_team_request().project_upload_id) == "98ea09b8-8d59-4e8c-8ffd-e89de1529ef5"
    with pytest.raises(ValueError, match="only valid for isolated access"):
        _team_request(
            folder_access="full_access",
            project_dir="/tmp/project",
            full_access_acknowledged=True,
            default_workspace_policy="worktree",
        )
    with pytest.raises(ValueError, match="only valid for isolated access"):
        _team_request(project_dir="/tmp/project")


def test_missing_project_upload_fails_closed(monkeypatch, tmp_path):
    _configure_root(monkeypatch, tmp_path)
    with pytest.raises(ProjectUploadError, match="missing"):
        resolve_project_upload("98ea09b8-8d59-4e8c-8ffd-e89de1529ef5")


def test_project_upload_endpoint_requires_auth_and_returns_only_summary(monkeypatch, tmp_path):
    _configure_root(monkeypatch, tmp_path)
    with TestClient(app) as client:
        assert client.post("/api/project-uploads").status_code == 401
        response = client.post(
            "/api/project-uploads",
            headers={"Authorization": f"Bearer {settings.api_token}"},
            files=[("files", ("main.py", b"print('ok')", "text/plain"))],
            data={"paths": "demo/main.py"},
        )
    assert response.status_code == 201, response.text
    assert response.json()["file_count"] == 1
    assert response.json()["total_bytes"] == 11
    assert "path" not in response.json()
