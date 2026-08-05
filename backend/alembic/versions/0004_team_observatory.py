"""team observatory: message state machine, audit events, progress signals, container-scoped events

Revision ID: 0004_team_observatory
Revises: 0003_agent_team_presets
Create Date: 2026-08-04 12:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision: str = "0004_team_observatory"
down_revision: Union[str, None] = "0003_agent_team_presets"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. session_messages: add message_type and acknowledged_at (idempotent)
    op.execute("ALTER TABLE session_messages ADD COLUMN IF NOT EXISTS message_type VARCHAR(32) NOT NULL DEFAULT 'message'")
    op.execute("ALTER TABLE session_messages ADD COLUMN IF NOT EXISTS acknowledged_at TIMESTAMPTZ")
    op.execute("ALTER TABLE session_messages ADD COLUMN IF NOT EXISTS injection_count INTEGER NOT NULL DEFAULT 0")

    # 2. execution_events: add container_id (idempotent)
    op.execute("ALTER TABLE execution_events ADD COLUMN IF NOT EXISTS container_id UUID REFERENCES work_containers(id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_events_container_seq ON execution_events(container_id, seq)")

    # 3. Create team_audit_events table (idempotent)
    op.execute("""
        CREATE TABLE IF NOT EXISTS team_audit_events (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            container_id UUID NOT NULL REFERENCES work_containers(id),
            session_id UUID REFERENCES work_sessions(id),
            action VARCHAR(64) NOT NULL,
            old_value JSONB,
            new_value JSONB,
            operator VARCHAR(256) NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_team_audit_events_container_id ON team_audit_events(container_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_team_audit_events_session_id ON team_audit_events(session_id)")

    # 4. Create session_progress_signals table (idempotent)
    op.execute("""
        CREATE TABLE IF NOT EXISTS session_progress_signals (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            session_id UUID NOT NULL REFERENCES work_sessions(id) ON DELETE CASCADE,
            run_id UUID NOT NULL REFERENCES task_runs(id),
            summary TEXT,
            milestone VARCHAR(500),
            completed_items JSONB,
            next_step TEXT,
            blocked BOOLEAN NOT NULL DEFAULT false,
            blocker_reason TEXT,
            needs_operator BOOLEAN NOT NULL DEFAULT false,
            evidence TEXT,
            iteration INTEGER NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_session_progress_signals_session_id ON session_progress_signals(session_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_session_progress_signals_run_id ON session_progress_signals(run_id)")


def downgrade() -> None:
    op.drop_table("session_progress_signals")
    op.drop_table("team_audit_events")
    op.execute("ALTER TABLE execution_events DROP COLUMN IF EXISTS container_id")
    op.execute("ALTER TABLE session_messages DROP COLUMN IF EXISTS acknowledged_at")
    op.execute("ALTER TABLE session_messages DROP COLUMN IF EXISTS injection_count")
    op.execute("ALTER TABLE session_messages DROP COLUMN IF EXISTS message_type")
