"""add agent team preset provenance and idempotency

Revision ID: 0003_agent_team_presets
Revises: 0002_work_containers
"""
from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0003_agent_team_presets"
down_revision = "0002_work_containers"
branch_labels = None
depends_on = None


def _column_names(table: str) -> set[str]:
    return {column["name"] for column in sa.inspect(op.get_bind()).get_columns(table)}


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if "work_containers" not in inspector.get_table_names():
        return
    columns = _column_names("work_containers")
    additions = {
        "preset_id": sa.Column("preset_id", sa.String(100), nullable=True),
        "preset_version": sa.Column("preset_version", sa.Integer(), nullable=True),
        "preset_snapshot": sa.Column(
            "preset_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
        "idempotency_key": sa.Column("idempotency_key", sa.String(100), nullable=True),
    }
    for name, column in additions.items():
        if name not in columns:
            op.add_column("work_containers", column)

    unique_names = {
        constraint.get("name")
        for constraint in sa.inspect(op.get_bind()).get_unique_constraints("work_containers")
    }
    if "uq_work_containers_idempotency_key" not in unique_names:
        op.create_unique_constraint(
            "uq_work_containers_idempotency_key", "work_containers", ["idempotency_key"]
        )


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if "work_containers" not in inspector.get_table_names():
        return
    unique_names = {
        constraint.get("name")
        for constraint in inspector.get_unique_constraints("work_containers")
    }
    if "uq_work_containers_idempotency_key" in unique_names:
        op.drop_constraint(
            "uq_work_containers_idempotency_key", "work_containers", type_="unique"
        )
    columns = _column_names("work_containers")
    for name in ("idempotency_key", "preset_snapshot", "preset_version", "preset_id"):
        if name in columns:
            op.drop_column("work_containers", name)
