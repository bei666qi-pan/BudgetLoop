"""initial schema

首版迁移直接以 SQLAlchemy 元数据建表，保证 schema 与模型严格一致；
后续变更再追加增量迁移。

Revision ID: 0001_initial
"""
from __future__ import annotations

from alembic import op

from app.core.models import Base

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    Base.metadata.create_all(bind=op.get_bind())


def downgrade() -> None:
    Base.metadata.drop_all(bind=op.get_bind())
