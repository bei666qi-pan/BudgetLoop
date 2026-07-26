"""LocalVolumeArtifactStore 读写与路径穿越防护（纯本地，无需 docker）。"""
from __future__ import annotations

import pytest

from app.artifacts import store as store_module
from app.artifacts.store import ArtifactNotFound, LocalVolumeArtifactStore, get_store
from app.core.config import settings


def test_put_get_roundtrip(tmp_path):
    store = LocalVolumeArtifactStore(tmp_path)
    ref = store.put_bytes("runs/abc/llm/1.json", b'{"ok": true}')
    assert ref == "runs/abc/llm/1.json"
    assert store.get_bytes(ref) == b'{"ok": true}'
    assert (tmp_path / "runs/abc/llm/1.json").is_file()


def test_get_missing_raises_not_found(tmp_path):
    store = LocalVolumeArtifactStore(tmp_path)
    with pytest.raises(ArtifactNotFound):
        store.get_bytes("nope.bin")


@pytest.mark.parametrize("key", ["../evil", "a/../../evil", "/etc/passwd", "runs/../../x"])
def test_path_traversal_rejected(tmp_path, key):
    store = LocalVolumeArtifactStore(tmp_path)
    with pytest.raises(ValueError, match="escapes"):
        store.put_bytes(key, b"x")
    with pytest.raises(ValueError, match="escapes"):
        store.get_bytes(key)


def test_traversal_cannot_escape_via_put(tmp_path):
    store = LocalVolumeArtifactStore(tmp_path / "sub")
    with pytest.raises(ValueError):
        store.put_bytes("../outside.txt", b"x")
    assert not (tmp_path / "outside.txt").exists()


def test_get_store_local_default(monkeypatch):
    monkeypatch.setattr(store_module, "_store", None)
    monkeypatch.setattr(settings, "artifact_backend", "local")
    assert isinstance(get_store(), LocalVolumeArtifactStore)
    monkeypatch.setattr(store_module, "_store", None)


def test_get_store_unknown_backend(monkeypatch):
    monkeypatch.setattr(store_module, "_store", None)
    monkeypatch.setattr(settings, "artifact_backend", "bogus")
    with pytest.raises(ValueError, match="unknown artifact_backend"):
        get_store()
    monkeypatch.setattr(store_module, "_store", None)
