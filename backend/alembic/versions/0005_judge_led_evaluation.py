"""judge-led team evaluation loop

Revision ID: 0005_judge_led_evaluation
Revises: 0004_team_observatory
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0005_judge_led_evaluation"
down_revision: Union[str, None] = "0004_team_observatory"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE work_sessions ADD COLUMN IF NOT EXISTS session_kind VARCHAR(30) NOT NULL DEFAULT 'agent'")
    op.execute("ALTER TABLE work_sessions ADD COLUMN IF NOT EXISTS system_managed BOOLEAN NOT NULL DEFAULT false")
    op.execute("CREATE INDEX IF NOT EXISTS ix_work_sessions_session_kind ON work_sessions(session_kind)")
    op.execute("""
        CREATE TABLE IF NOT EXISTS judge_policies (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            container_id UUID NOT NULL UNIQUE REFERENCES work_containers(id) ON DELETE CASCADE,
            gates JSONB NOT NULL DEFAULT '[]'::jsonb,
            model_config JSONB NOT NULL DEFAULT '{}'::jsonb,
            safety_limits JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_judge_policies_container_id ON judge_policies(container_id)")
    op.execute("""
        CREATE TABLE IF NOT EXISTS judge_rounds (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            container_id UUID NOT NULL REFERENCES work_containers(id) ON DELETE CASCADE,
            judge_session_id UUID NOT NULL REFERENCES work_sessions(id) ON DELETE CASCADE,
            sequence INTEGER NOT NULL,
            request_key VARCHAR(100),
            status VARCHAR(30) NOT NULL DEFAULT 'collecting',
            phase VARCHAR(30) NOT NULL DEFAULT 'evidence',
            verdict VARCHAR(20), summary TEXT,
            evidence_refs JSONB NOT NULL DEFAULT '[]'::jsonb,
            evidence_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
            model_verdict JSONB,
            feedback_message_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
            pending_session_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT uq_judge_round_container_sequence UNIQUE(container_id, sequence),
            CONSTRAINT uq_judge_round_container_request_key UNIQUE(container_id, request_key)
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_judge_rounds_container_id ON judge_rounds(container_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_judge_rounds_judge_session_id ON judge_rounds(judge_session_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_judge_rounds_status ON judge_rounds(status)")
    op.execute("""
        CREATE TABLE IF NOT EXISTS judge_gate_results (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            round_id UUID NOT NULL REFERENCES judge_rounds(id) ON DELETE CASCADE,
            gate_name VARCHAR(100) NOT NULL, passed BOOLEAN NOT NULL,
            evidence JSONB NOT NULL DEFAULT '{}'::jsonb,
            failure_reason TEXT, created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_judge_gate_results_round_id ON judge_gate_results(round_id)")
    op.execute("""
        CREATE TABLE IF NOT EXISTS judge_findings (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            round_id UUID NOT NULL REFERENCES judge_rounds(id) ON DELETE CASCADE,
            responsible_session_id UUID REFERENCES work_sessions(id) ON DELETE SET NULL,
            severity VARCHAR(20) NOT NULL DEFAULT 'medium', summary TEXT NOT NULL,
            evidence_refs JSONB NOT NULL DEFAULT '[]'::jsonb, feedback TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_judge_findings_round_id ON judge_findings(round_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_judge_findings_responsible_session_id ON judge_findings(responsible_session_id)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS judge_findings")
    op.execute("DROP TABLE IF EXISTS judge_gate_results")
    op.execute("DROP TABLE IF EXISTS judge_rounds")
    op.execute("DROP TABLE IF EXISTS judge_policies")
    op.execute("DROP INDEX IF EXISTS ix_work_sessions_session_kind")
    op.execute("ALTER TABLE work_sessions DROP COLUMN IF EXISTS system_managed")
    op.execute("ALTER TABLE work_sessions DROP COLUMN IF EXISTS session_kind")
