from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from app.core.models import SessionMessage, WorkContainer, WorkSession

pytestmark = pytest.mark.unit


def test_collaboration_tables_define_expected_constraints_and_indexes():
    assert WorkContainer.__table__.c.lifecycle_state.default.arg == "active"
    assert WorkSession.__table__.c.worktree_enabled.default.arg is False
    assert SessionMessage.__table__.c.delivery_state.default.arg == "queued"
    assert any(
        constraint.name == "uq_work_session_container_key"
        for constraint in WorkSession.__table__.constraints
    )
    assert any(
        constraint.name == "uq_session_message_container_key"
        for constraint in SessionMessage.__table__.constraints
    )
    assert "ix_session_messages_recipient_delivery_created" in {
        index.name for index in SessionMessage.__table__.indexes
    }
    assert WorkContainer.__table__.c.preset_id.nullable is True
    assert WorkContainer.__table__.c.preset_version.nullable is True
    assert WorkContainer.__table__.c.preset_snapshot.nullable is True
    assert WorkContainer.__table__.c.idempotency_key.unique is True


def test_container_foreign_keys_fail_closed_or_cascade_as_designed():
    session_container_fk = next(iter(WorkSession.__table__.c.container_id.foreign_keys))
    message_container_fk = next(iter(SessionMessage.__table__.c.container_id.foreign_keys))
    sender_fk = next(iter(SessionMessage.__table__.c.sender_session_id.foreign_keys))
    recipient_fk = next(iter(SessionMessage.__table__.c.recipient_session_id.foreign_keys))
    assert session_container_fk.ondelete == "CASCADE"
    assert message_container_fk.ondelete == "CASCADE"
    assert sender_fk.ondelete == "SET NULL"
    assert recipient_fk.ondelete == "CASCADE"


def test_migration_revision_is_incremental_and_reversible():
    path = Path(__file__).parents[1] / "alembic" / "versions" / "0002_work_containers.py"
    spec = importlib.util.spec_from_file_location("budgetloop_migration_0002", path)
    assert spec and spec.loader
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    assert migration.revision == "0002_work_containers"
    assert migration.down_revision == "0001_initial"
    assert callable(migration.upgrade)
    assert callable(migration.downgrade)


def test_preset_migration_is_incremental_and_reversible():
    path = Path(__file__).parents[1] / "alembic" / "versions" / "0003_agent_team_presets.py"
    spec = importlib.util.spec_from_file_location("budgetloop_migration_0003", path)
    assert spec and spec.loader
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    assert migration.revision == "0003_agent_team_presets"
    assert migration.down_revision == "0002_work_containers"
    assert callable(migration.upgrade)
    assert callable(migration.downgrade)
