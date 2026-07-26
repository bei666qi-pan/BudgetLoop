"""add work containers, sessions and explicit collaboration inbox

Revision ID: 0002_work_containers
Revises: 0001_initial
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0002_work_containers"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 0001 historically imports current metadata. The guards keep fresh installs
    # safe while still applying this migration to existing 0001 databases.
    existing = set(sa.inspect(op.get_bind()).get_table_names())
    if "work_containers" not in existing:
        op.create_table(
            "work_containers",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column("name", sa.String(200), nullable=False),
            sa.Column("project_goal", sa.Text(), nullable=False),
            sa.Column("shared_context", sa.Text(), nullable=False),
            sa.Column("lifecycle_state", sa.String(20), nullable=False),
            sa.Column("base_workdir", sa.String(500), nullable=False),
            sa.Column("default_workspace_policy", sa.String(20), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index("ix_work_containers_lifecycle_state", "work_containers", ["lifecycle_state"])

    if "work_sessions" not in existing:
        op.create_table(
            "work_sessions",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column("container_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("role", sa.String(120), nullable=False),
            sa.Column("goal", sa.Text(), nullable=False),
            sa.Column("private_context", sa.Text(), nullable=False),
            sa.Column("status", sa.String(30), nullable=False),
            sa.Column("task_id", postgresql.UUID(as_uuid=True), nullable=False, unique=True),
            sa.Column("current_run_id", postgresql.UUID(as_uuid=True), nullable=False, unique=True),
            sa.Column("conversation_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("worktree_enabled", sa.Boolean(), nullable=False),
            sa.Column("worktree_branch", sa.String(200), nullable=True),
            sa.Column("worktree_path", sa.String(500), nullable=True),
            sa.Column("workspace_status", sa.String(30), nullable=False),
            sa.Column("workspace_error", sa.Text(), nullable=True),
            sa.Column("idempotency_key", sa.String(100), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["container_id"], ["work_containers.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["task_id"], ["tasks.id"]),
            sa.ForeignKeyConstraint(["current_run_id"], ["task_runs.id"]),
            sa.UniqueConstraint("container_id", "idempotency_key", name="uq_work_session_container_key"),
        )
        op.create_index("ix_work_sessions_container_id", "work_sessions", ["container_id"])
        op.create_index("ix_work_sessions_status", "work_sessions", ["status"])

    if "session_messages" not in existing:
        op.create_table(
            "session_messages",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column("container_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("sender_session_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("recipient_session_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("author_type", sa.String(20), nullable=False),
            sa.Column("kind", sa.String(20), nullable=False),
            sa.Column("content", sa.Text(), nullable=False),
            sa.Column("delivery_state", sa.String(20), nullable=False),
            sa.Column("idempotency_key", sa.String(100), nullable=True),
            sa.Column("message_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(["container_id"], ["work_containers.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["sender_session_id"], ["work_sessions.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["recipient_session_id"], ["work_sessions.id"], ondelete="CASCADE"),
            sa.UniqueConstraint("container_id", "idempotency_key", name="uq_session_message_container_key"),
        )
        op.create_index("ix_session_messages_container_id", "session_messages", ["container_id"])
        op.create_index("ix_session_messages_sender_session_id", "session_messages", ["sender_session_id"])
        op.create_index("ix_session_messages_recipient_session_id", "session_messages", ["recipient_session_id"])
        op.create_index("ix_session_messages_delivery_state", "session_messages", ["delivery_state"])
        op.create_index(
            "ix_session_messages_recipient_delivery_created",
            "session_messages",
            ["recipient_session_id", "delivery_state", "created_at"],
        )


def downgrade() -> None:
    existing = set(sa.inspect(op.get_bind()).get_table_names())
    if "session_messages" in existing:
        op.drop_table("session_messages")
    if "work_sessions" in existing:
        op.drop_table("work_sessions")
    if "work_containers" in existing:
        op.drop_table("work_containers")
