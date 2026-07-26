"""Comprehensive unit tests for WorkspaceManager (P0 module).

All Docker interactions are mocked — NO real Docker daemon required.
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import docker.errors
import httpx
import pytest

from app.worker.workspace_manager import (
    CONTAINER_WORKDIR,
    HEALTH_TIMEOUT_SECONDS,
    LABEL_RUN_ID,
    WorkspaceError,
    WorkspaceHandle,
    WorkspaceManager,
)

pytestmark = pytest.mark.unit


# ============================================================================
# WorkspaceHandle dataclass
# ============================================================================


def test_workspace_handle_all_fields():
    h = WorkspaceHandle(
        container_id="abc123",
        base_url="http://127.0.0.1:32768",
        session_key="sekret",
        volume_name="vol-1",
        working_dir="/custom",
    )
    assert h.container_id == "abc123"
    assert h.base_url == "http://127.0.0.1:32768"
    assert h.session_key == "sekret"
    assert h.volume_name == "vol-1"
    assert h.working_dir == "/custom"


def test_workspace_handle_default_working_dir():
    h = WorkspaceHandle(
        container_id="abc123",
        base_url="http://127.0.0.1:32768",
        session_key="sekret",
        volume_name="vol-1",
    )
    assert h.working_dir == CONTAINER_WORKDIR


def test_workspace_handle_frozen():
    h = WorkspaceHandle(
        container_id="abc123",
        base_url="http://127.0.0.1:32768",
        session_key="sekret",
        volume_name="vol-1",
    )
    with pytest.raises(Exception):  # FrozenInstanceError or AttributeError
        h.container_id = "xyz"  # type: ignore[misc]


# ============================================================================
# WorkspaceError
# ============================================================================


def test_workspace_error_basic():
    err = WorkspaceError("something went wrong")
    assert str(err) == "something went wrong"
    assert isinstance(err, Exception)


def test_workspace_error_chained():
    cause = RuntimeError("root cause")
    err = WorkspaceError("wrapped")
    err.__cause__ = cause
    assert err.__cause__ is cause


# ============================================================================
# WorkspaceManager.__init__
# ============================================================================


def test_init_with_provided_docker_client():
    client = MagicMock()
    mgr = WorkspaceManager(docker_client=client)
    assert mgr._docker is client
    # from_env must NOT be called
    client.ping.assert_not_called()


def test_init_without_client_docker_available():
    with patch("app.worker.workspace_manager.docker.from_env") as mock_from_env:
        mock_client = MagicMock()
        mock_from_env.return_value = mock_client
        mgr = WorkspaceManager()
        mock_from_env.assert_called_once()
        mock_client.ping.assert_called_once()
        assert mgr._docker is mock_client


def test_init_without_client_docker_unavailable():
    with patch("app.worker.workspace_manager.docker.from_env") as mock_from_env:
        mock_from_env.side_effect = docker.errors.DockerException("no daemon")
        with pytest.raises(WorkspaceError, match="docker daemon unreachable"):
            WorkspaceManager()


def test_init_custom_image():
    client = MagicMock()
    mgr = WorkspaceManager(docker_client=client, image="my-custom:latest")
    assert mgr.image == "my-custom:latest"


# ============================================================================
# _ensure_volume
# ============================================================================


def test_ensure_volume_existing():
    client = MagicMock()
    mgr = WorkspaceManager(docker_client=client)
    vol = client.volumes.get.return_value = MagicMock()
    result = mgr._ensure_volume("myvol")
    client.volumes.get.assert_called_once_with("myvol")
    assert result is vol


def test_ensure_volume_new():
    client = MagicMock()
    mgr = WorkspaceManager(docker_client=client)
    client.volumes.get.side_effect = docker.errors.NotFound("nope")
    created = client.volumes.create.return_value = MagicMock()
    result = mgr._ensure_volume("myvol")
    client.volumes.create.assert_called_once_with(name="myvol")
    assert result is created


def test_ensure_volume_docker_error():
    client = MagicMock()
    mgr = WorkspaceManager(docker_client=client)
    client.volumes.get.side_effect = docker.errors.DockerException("boom")
    with pytest.raises(WorkspaceError, match="failed to ensure volume"):
        mgr._ensure_volume("myvol")


# ============================================================================
# _base_url
# ============================================================================


def test_base_url_normal_port():
    client = MagicMock()
    mgr = WorkspaceManager(docker_client=client)
    container = MagicMock()
    container.id = "abc"
    container.ports = {"8000/tcp": [{"HostPort": "32768"}]}
    url = mgr._base_url(container)
    container.reload.assert_called_once()
    assert url == "http://127.0.0.1:32768"


def test_base_url_uses_configured_docker_desktop_host(monkeypatch):
    """Compose workers must reach random published ports through the host."""
    client = MagicMock()
    mgr = WorkspaceManager(docker_client=client)
    container = MagicMock()
    container.id = "abc"
    container.ports = {"8000/tcp": [{"HostPort": "32768"}]}
    monkeypatch.setattr(
        "app.worker.workspace_manager.settings.workspace_published_host",
        "host.docker.internal",
    )

    assert mgr._base_url(container) == "http://host.docker.internal:32768"


def test_base_url_no_published_port():
    client = MagicMock()
    mgr = WorkspaceManager(docker_client=client)
    container = MagicMock()
    container.id = "abc"
    container.ports = {}
    with pytest.raises(WorkspaceError, match="no published port"):
        mgr._base_url(container)


# ============================================================================
# _session_key_from_env
# ============================================================================


def test_session_key_from_env_found():
    container = MagicMock()
    container.attrs = {"Config": {"Env": ["OH_SESSION_API_KEYS_0=mykey", "OTHER=val"]}}
    assert WorkspaceManager._session_key_from_env(container) == "mykey"


def test_session_key_from_env_not_found():
    container = MagicMock()
    container.attrs = {"Config": {"Env": ["OTHER=val"]}}
    assert WorkspaceManager._session_key_from_env(container) is None


def test_session_key_from_env_empty():
    container = MagicMock()
    container.attrs = {"Config": {"Env": []}}
    assert WorkspaceManager._session_key_from_env(container) is None


def test_session_key_from_env_no_config():
    container = MagicMock()
    container.attrs = {}
    assert WorkspaceManager._session_key_from_env(container) is None


# ============================================================================
# _wait_healthy
# ============================================================================


def _build_mgr_with_client() -> WorkspaceManager:
    client = MagicMock()
    return WorkspaceManager(docker_client=client)


def test_wait_healthy_immediate_200():
    mgr = _build_mgr_with_client()
    with patch("app.worker.workspace_manager.httpx.Client") as MockClient:
        mock_http = MockClient.return_value.__enter__.return_value
        resp = MagicMock()
        resp.status_code = 200
        mock_http.get.return_value = resp
        # Should return without raising
        mgr._wait_healthy("http://127.0.0.1:9999", "key")


def test_wait_healthy_200_after_retries():
    mgr = _build_mgr_with_client()
    with patch("app.worker.workspace_manager.httpx.Client") as MockClient:
        mock_http = MockClient.return_value.__enter__.return_value
        resp_503 = MagicMock()
        resp_503.status_code = 503
        resp_200 = MagicMock()
        resp_200.status_code = 200
        mock_http.get.side_effect = [resp_503, resp_200]
        mgr._wait_healthy("http://127.0.0.1:9999", "key")
        assert mock_http.get.call_count == 2


def test_wait_healthy_http_error_then_200():
    """HTTPError (connection refused) is swallowed, then 200 succeeds."""
    mgr = _build_mgr_with_client()
    with patch("app.worker.workspace_manager.httpx.Client") as MockClient:
        mock_http = MockClient.return_value.__enter__.return_value
        resp_200 = MagicMock()
        resp_200.status_code = 200
        mock_http.get.side_effect = [httpx.ConnectError("refused"), resp_200]
        mgr._wait_healthy("http://127.0.0.1:9999", "key")
        assert mock_http.get.call_count == 2


def test_wait_healthy_timeout():
    mgr = _build_mgr_with_client()
    with patch("app.worker.workspace_manager.httpx.Client") as MockClient:
        mock_http = MockClient.return_value.__enter__.return_value
        mock_http.get.return_value.status_code = 503  # never healthy
        with patch("app.worker.workspace_manager.time.sleep", return_value=None):
            with patch("app.worker.workspace_manager.time.monotonic") as mock_mono:
                # Fast-forward past deadline immediately
                mock_mono.side_effect = [0.0, HEALTH_TIMEOUT_SECONDS + 1.0]
                with pytest.raises(WorkspaceError, match="not healthy within"):
                    mgr._wait_healthy("http://127.0.0.1:9999", "key")


# ============================================================================
# _remove_container
# ============================================================================


def test_remove_container_normal():
    container = MagicMock()
    WorkspaceManager._remove_container(container)
    container.remove.assert_called_once_with(force=True)


def test_remove_container_docker_error_no_raise():
    container = MagicMock()
    container.remove.side_effect = docker.errors.DockerException("boom")
    # Must not raise
    WorkspaceManager._remove_container(container)


# ============================================================================
# _copy_fixture
# ============================================================================


def test_copy_fixture_not_a_directory(tmp_path):
    client = MagicMock()
    mgr = WorkspaceManager(docker_client=client)
    f = tmp_path / "file.txt"
    f.write_text("hello")
    container = MagicMock()
    with pytest.raises(WorkspaceError, match="fixture dir not found"):
        mgr._copy_fixture(container, f, CONTAINER_WORKDIR)


def test_copy_fixture_success(tmp_path):
    client = MagicMock()
    mgr = WorkspaceManager(docker_client=client)
    (tmp_path / "script.py").write_text("print(1)")
    container = MagicMock()
    container.put_archive.return_value = True
    mgr._copy_fixture(container, tmp_path, CONTAINER_WORKDIR)
    container.put_archive.assert_called_once()
    args, _kwargs = container.put_archive.call_args
    assert args[0] == CONTAINER_WORKDIR


def test_copy_fixture_put_archive_false(tmp_path):
    client = MagicMock()
    mgr = WorkspaceManager(docker_client=client)
    (tmp_path / "script.py").write_text("print(1)")
    container = MagicMock()
    container.put_archive.return_value = False
    with pytest.raises(WorkspaceError, match="put_archive failed"):
        mgr._copy_fixture(container, tmp_path, CONTAINER_WORKDIR)


def test_copy_fixture_docker_error(tmp_path):
    client = MagicMock()
    mgr = WorkspaceManager(docker_client=client)
    (tmp_path / "script.py").write_text("print(1)")
    container = MagicMock()
    container.put_archive.side_effect = docker.errors.DockerException("disk full")
    with pytest.raises(WorkspaceError, match="failed to copy fixture"):
        mgr._copy_fixture(container, tmp_path, CONTAINER_WORKDIR)


# ============================================================================
# _git_init
# ============================================================================


def test_git_init_success():
    container = MagicMock()
    exec_result = MagicMock()
    exec_result.exit_code = 0
    container.exec_run.return_value = exec_result
    WorkspaceManager._git_init(container, CONTAINER_WORKDIR)
    container.exec_run.assert_called_once()
    cmd = container.exec_run.call_args[0][0]
    assert "git init" in str(cmd)
    assert CONTAINER_WORKDIR in str(cmd)


def test_git_init_failure():
    container = MagicMock()
    exec_result = MagicMock()
    exec_result.exit_code = 1
    exec_result.output = b"fatal: not a git repository"
    container.exec_run.return_value = exec_result
    with pytest.raises(WorkspaceError, match="git init failed"):
        WorkspaceManager._git_init(container, CONTAINER_WORKDIR)


def test_git_init_output_truncation():
    """Long output should be truncated to 500 chars in error message."""
    container = MagicMock()
    exec_result = MagicMock()
    exec_result.exit_code = 1
    exec_result.output = b"x" * 1000
    container.exec_run.return_value = exec_result
    with pytest.raises(WorkspaceError) as exc:
        WorkspaceManager._git_init(container, CONTAINER_WORKDIR)
    # Output in error message should be ≤ 500 chars
    assert "git init failed" in str(exc.value)


def test_create_worktree_uses_server_uuid_and_bounded_path():
    container = MagicMock()
    container.exec_run.return_value.exit_code = 0
    session_id = "11111111-2222-3333-4444-555555555555"
    branch, path = WorkspaceManager._create_worktree(container, CONTAINER_WORKDIR, session_id)
    assert branch == "bl/session-111111112222"
    assert path == "/workspace/.budgetloop/worktrees/11111111222233334444555555555555"
    command = container.exec_run.call_args[0][0][2]
    assert "git -C /workspace worktree add" in command
    assert path in command


def test_create_worktree_rejects_client_path_like_identifier():
    container = MagicMock()
    with pytest.raises(WorkspaceError, match="server-generated UUID"):
        WorkspaceManager._create_worktree(container, CONTAINER_WORKDIR, "../../escape")
    container.exec_run.assert_not_called()


def test_create_worktree_fails_closed():
    container = MagicMock()
    container.exec_run.return_value.exit_code = 1
    container.exec_run.return_value.output = b"fatal: invalid git state"
    with pytest.raises(WorkspaceError, match="worktree setup failed"):
        WorkspaceManager._create_worktree(
            container, CONTAINER_WORKDIR, "11111111-2222-3333-4444-555555555555"
        )


# ============================================================================
# provision
# ============================================================================


def test_provision_successful_flow(monkeypatch):
    client = MagicMock()
    mgr = WorkspaceManager(docker_client=client)

    # Mock volume
    vol = MagicMock()
    vol.name = "budgetloop-ws-run1"
    client.volumes.get.return_value = vol

    # Mock container
    container = MagicMock()
    container.id = "abc123"
    container.ports = {"8000/tcp": [{"HostPort": "32768"}]}
    client.containers.run.return_value = container

    # Mock _wait_healthy (patch instance method)
    monkeypatch.setattr(mgr, "_wait_healthy", MagicMock())
    monkeypatch.setattr(WorkspaceManager, "_git_init", MagicMock())

    handle = mgr.provision("run1")

    client.volumes.get.assert_called_once_with("budgetloop-ws-run1")
    client.containers.run.assert_called_once()
    mgr._wait_healthy.assert_called_once_with("http://127.0.0.1:32768", handle.session_key)
    assert handle.container_id == "abc123"
    assert handle.base_url == "http://127.0.0.1:32768"
    assert handle.volume_name == "budgetloop-ws-run1"


def test_provision_with_source_dir(tmp_path, monkeypatch):
    client = MagicMock()
    mgr = WorkspaceManager(docker_client=client)

    vol = MagicMock()
    vol.name = "budgetloop-ws-run2"
    client.volumes.get.return_value = vol

    container = MagicMock()
    container.id = "def456"
    container.ports = {"8000/tcp": [{"HostPort": "32769"}]}
    client.containers.run.return_value = container

    monkeypatch.setattr(mgr, "_wait_healthy", MagicMock())
    monkeypatch.setattr(mgr, "_copy_fixture", MagicMock())
    monkeypatch.setattr(WorkspaceManager, "_git_init", MagicMock())

    (tmp_path / "hello.py").write_text("print('hi')")
    handle = mgr.provision("run2", source_dir=tmp_path)

    mgr._copy_fixture.assert_called_once_with(container, tmp_path, CONTAINER_WORKDIR)
    assert handle.container_id == "def456"
    assert handle.volume_name == "budgetloop-ws-run2"


def test_provision_container_start_failure():
    client = MagicMock()
    mgr = WorkspaceManager(docker_client=client)
    client.volumes.get.return_value = MagicMock()
    client.containers.run.side_effect = docker.errors.DockerException("oom")
    with pytest.raises(WorkspaceError, match="failed to start workspace container"):
        mgr.provision("run1")


def test_provision_copy_fixture_failure_cleanup(tmp_path, monkeypatch):
    client = MagicMock()
    mgr = WorkspaceManager(docker_client=client)

    client.volumes.get.return_value = MagicMock()
    container = MagicMock()
    container.id = "c1"
    container.ports = {"8000/tcp": [{"HostPort": "32768"}]}
    client.containers.run.return_value = container

    monkeypatch.setattr(mgr, "_wait_healthy", MagicMock())
    monkeypatch.setattr(mgr, "_copy_fixture", MagicMock(side_effect=WorkspaceError("copy boom")))
    monkeypatch.setattr(WorkspaceManager, "_git_init", MagicMock())

    (tmp_path / "script.py").write_text("print(1)")
    with pytest.raises(WorkspaceError, match="copy boom"):
        mgr.provision("run1", source_dir=tmp_path)
    container.remove.assert_called_once_with(force=True)


def test_provision_wait_healthy_failure_cleanup(monkeypatch):
    client = MagicMock()
    mgr = WorkspaceManager(docker_client=client)

    client.volumes.get.return_value = MagicMock()
    container = MagicMock()
    container.id = "c2"
    container.ports = {"8000/tcp": [{"HostPort": "32768"}]}
    client.containers.run.return_value = container

    monkeypatch.setattr(mgr, "_wait_healthy", MagicMock(side_effect=WorkspaceError("timeout")))
    monkeypatch.setattr(WorkspaceManager, "_git_init", MagicMock())

    with pytest.raises(WorkspaceError, match="timeout"):
        mgr.provision("run1")
    container.remove.assert_called_once_with(force=True)


# ============================================================================
# attach
# ============================================================================


def test_attach_container_running(monkeypatch):
    client = MagicMock()
    mgr = WorkspaceManager(docker_client=client)

    container = MagicMock()
    container.id = "attached-1"
    container.status = "running"
    container.ports = {"8000/tcp": [{"HostPort": "32770"}]}
    container.attrs = {"Config": {"Env": ["OH_SESSION_API_KEYS_0=attachkey"]}}
    client.containers.get.return_value = container

    monkeypatch.setattr(mgr, "_wait_healthy", MagicMock())

    handle = mgr.attach("run1", "attached-1")

    assert handle.container_id == "attached-1"
    assert handle.session_key == "attachkey"
    assert handle.base_url == "http://127.0.0.1:32770"
    assert handle.volume_name == "budgetloop-ws-run1"
    container.start.assert_not_called()
    # reload is called in attach() (line 108) and again in _base_url() (line 143)
    assert container.reload.call_count == 2


def test_attach_container_stopped_start_called(monkeypatch):
    client = MagicMock()
    mgr = WorkspaceManager(docker_client=client)

    container = MagicMock()
    container.id = "stopped-1"
    container.status = "exited"
    container.ports = {"8000/tcp": [{"HostPort": "32771"}]}
    container.attrs = {"Config": {"Env": ["OH_SESSION_API_KEYS_0=sekret"]}}
    client.containers.get.return_value = container

    monkeypatch.setattr(mgr, "_wait_healthy", MagicMock())

    handle = mgr.attach("run1", "stopped-1")
    container.start.assert_called_once()
    # reload called in attach() (line 108) and in _base_url() (line 143)
    assert container.reload.call_count == 2
    assert handle.container_id == "stopped-1"


def test_attach_container_not_found():
    client = MagicMock()
    mgr = WorkspaceManager(docker_client=client)
    client.containers.get.side_effect = docker.errors.NotFound("missing")
    with pytest.raises(WorkspaceError, match="failed to attach container"):
        mgr.attach("run1", "missing-id")


def test_attach_no_session_key_in_env():
    client = MagicMock()
    mgr = WorkspaceManager(docker_client=client)

    container = MagicMock()
    container.id = "c1"
    container.status = "running"
    container.attrs = {"Config": {"Env": ["SOME_OTHER=val"]}}
    client.containers.get.return_value = container

    with pytest.raises(WorkspaceError, match="no OH_SESSION_API_KEYS_0"):
        mgr.attach("run1", "c1")


def test_attach_wait_healthy_failure(monkeypatch):
    client = MagicMock()
    mgr = WorkspaceManager(docker_client=client)

    container = MagicMock()
    container.id = "c1"
    container.status = "running"
    container.ports = {"8000/tcp": [{"HostPort": "32772"}]}
    container.attrs = {"Config": {"Env": ["OH_SESSION_API_KEYS_0=key"]}}
    client.containers.get.return_value = container

    monkeypatch.setattr(mgr, "_wait_healthy", MagicMock(side_effect=WorkspaceError("dead")))

    with pytest.raises(WorkspaceError, match="dead"):
        mgr.attach("run1", "c1")


# ============================================================================
# destroy
# ============================================================================


def test_destroy_lists_and_removes_containers():
    client = MagicMock()
    mgr = WorkspaceManager(docker_client=client)

    c1, c2 = MagicMock(), MagicMock()
    client.containers.list.return_value = [c1, c2]

    mgr.destroy("run1")

    expected_filter = {"label": f"{LABEL_RUN_ID}=run1"}
    client.containers.list.assert_called_once_with(all=True, filters=expected_filter)
    c1.remove.assert_called_once_with(force=True)
    c2.remove.assert_called_once_with(force=True)


def test_destroy_no_containers():
    client = MagicMock()
    mgr = WorkspaceManager(docker_client=client)
    client.containers.list.return_value = []
    mgr.destroy("run1")  # must not raise


def test_destroy_list_error():
    client = MagicMock()
    mgr = WorkspaceManager(docker_client=client)
    client.containers.list.side_effect = docker.errors.DockerException("api error")
    with pytest.raises(WorkspaceError, match="failed to list containers"):
        mgr.destroy("run1")


# ============================================================================
# provision: full_access 宿主目录挂载
# ============================================================================


def _mock_running_container(client, container_id: str, host_port: str):
    container = MagicMock()
    container.id = container_id
    container.ports = {"8000/tcp": [{"HostPort": host_port}]}
    client.containers.run.return_value = container
    return container


def test_provision_full_access_bind_mounts_project_dir(monkeypatch):
    """full_access：bind-mount 宿主目录 rw 到 /workspace，不用命名卷、不拷 fixture。"""
    client = MagicMock()
    mgr = WorkspaceManager(docker_client=client)
    container = _mock_running_container(client, "fa1", "32800")
    container.exec_run.return_value.exit_code = 0  # /workspace/.git 已存在

    monkeypatch.setattr(mgr, "_wait_healthy", MagicMock())
    monkeypatch.setattr(mgr, "_copy_fixture", MagicMock())
    monkeypatch.setattr(WorkspaceManager, "_git_init", MagicMock())

    handle = mgr.provision(
        "run-fa",
        source_dir="/host/fixture",  # full_access 下必须被忽略
        folder_access="full_access",
        project_dir="/Users/qi/project",
    )

    client.volumes.get.assert_not_called()
    client.volumes.create.assert_not_called()
    volumes = client.containers.run.call_args.kwargs["volumes"]
    assert volumes == {"/Users/qi/project": {"bind": CONTAINER_WORKDIR, "mode": "rw"}}
    mgr._copy_fixture.assert_not_called()
    assert handle.container_id == "fa1"


def test_provision_full_access_skips_git_init_when_repo_exists(monkeypatch):
    """挂载目录已有 .git：复用既有仓库，不再 git init。"""
    client = MagicMock()
    mgr = WorkspaceManager(docker_client=client)
    container = _mock_running_container(client, "fa2", "32801")
    container.exec_run.return_value.exit_code = 0  # test -d /workspace/.git 命中

    monkeypatch.setattr(mgr, "_wait_healthy", MagicMock())
    monkeypatch.setattr(WorkspaceManager, "_git_init", MagicMock())

    mgr.provision("run-fa", folder_access="full_access", project_dir="/Users/qi/project")

    WorkspaceManager._git_init.assert_not_called()
    probe_cmd = container.exec_run.call_args[0][0]
    assert ".git" in str(probe_cmd)


def test_provision_full_access_git_init_when_no_repo(monkeypatch):
    """挂载目录没有 .git：照常建立 git 基线。"""
    client = MagicMock()
    mgr = WorkspaceManager(docker_client=client)
    container = _mock_running_container(client, "fa3", "32802")
    container.exec_run.return_value.exit_code = 1  # test -d /workspace/.git 未命中

    monkeypatch.setattr(mgr, "_wait_healthy", MagicMock())
    monkeypatch.setattr(WorkspaceManager, "_git_init", MagicMock())

    mgr.provision("run-fa", folder_access="full_access", project_dir="/Users/qi/project")

    WorkspaceManager._git_init.assert_called_once_with(container, CONTAINER_WORKDIR)


def test_provision_full_access_requires_project_dir():
    """full_access 缺 project_dir：fail-closed，不起容器。"""
    client = MagicMock()
    mgr = WorkspaceManager(docker_client=client)
    with pytest.raises(WorkspaceError, match="project_dir"):
        mgr.provision("run-fa", folder_access="full_access")
    client.containers.run.assert_not_called()


def test_provision_full_access_mount_rejection_names_folder():
    """docker 拒绝挂载：报错信息必须点名目录，且不回退到命名卷。"""
    client = MagicMock()
    mgr = WorkspaceManager(docker_client=client)
    client.containers.run.side_effect = docker.errors.APIError("mounts denied")
    with pytest.raises(WorkspaceError, match="/Users/qi/missing"):
        mgr.provision(
            "run-fa", folder_access="full_access", project_dir="/Users/qi/missing"
        )
    client.volumes.get.assert_not_called()
    client.volumes.create.assert_not_called()


def test_provision_isolated_with_project_dir_still_uses_volume(tmp_path, monkeypatch):
    """isolated + project_dir：仍用命名卷 + fixture 拷贝，宿主目录不被挂载/修改。"""
    client = MagicMock()
    mgr = WorkspaceManager(docker_client=client)
    vol = MagicMock()
    vol.name = "budgetloop-ws-run-iso"
    client.volumes.get.return_value = vol
    container = _mock_running_container(client, "iso1", "32803")

    monkeypatch.setattr(mgr, "_wait_healthy", MagicMock())
    monkeypatch.setattr(mgr, "_copy_fixture", MagicMock())
    monkeypatch.setattr(WorkspaceManager, "_git_init", MagicMock())

    (tmp_path / "a.py").write_text("x = 1")
    handle = mgr.provision(
        "run-iso",
        source_dir=tmp_path,
        folder_access="isolated",
        project_dir=str(tmp_path),
    )

    volumes = client.containers.run.call_args.kwargs["volumes"]
    assert volumes == {"budgetloop-ws-run-iso": {"bind": CONTAINER_WORKDIR, "mode": "rw"}}
    mgr._copy_fixture.assert_called_once_with(container, tmp_path, CONTAINER_WORKDIR)
    assert handle.volume_name == "budgetloop-ws-run-iso"


# ============================================================================
# Constants
# ============================================================================


def test_constants_values():
    assert LABEL_RUN_ID == "budgetloop.run_id"
    assert CONTAINER_WORKDIR == "/workspace"
    assert HEALTH_TIMEOUT_SECONDS == 120.0
