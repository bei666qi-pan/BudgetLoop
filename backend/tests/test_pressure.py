"""压力模式测试：双时间口径、token 紧张兜底。"""
from datetime import datetime, timedelta, timezone

from app.core.enums import PressureMode
from app.policy.pressure import compute_pressure_mode


class TestComputePressureMode:
    def test_normal(self):
        now = datetime.now(timezone.utc)
        mode = compute_pressure_mode(
            deadline_at=now + timedelta(seconds=1000),
            max_wall_time_seconds=1200,
            active_runtime_ms=100_000,
            max_active_runtime_seconds=600,
            remaining_tokens=80_000,
            max_total_tokens=100_000,
            now=now,
        )
        assert mode == PressureMode.NORMAL

    def test_conservative_wall(self):
        now = datetime.now(timezone.utc)
        mode = compute_pressure_mode(
            deadline_at=now + timedelta(seconds=500),
            max_wall_time_seconds=1200,
            active_runtime_ms=100_000,
            max_active_runtime_seconds=600,
            remaining_tokens=80_000,
            max_total_tokens=100_000,
            now=now,
        )
        assert mode == PressureMode.CONSERVATIVE

    def test_critical(self):
        now = datetime.now(timezone.utc)
        mode = compute_pressure_mode(
            deadline_at=now + timedelta(seconds=100),
            max_wall_time_seconds=1200,
            active_runtime_ms=550_000,
            max_active_runtime_seconds=600,
            remaining_tokens=80_000,
            max_total_tokens=100_000,
            now=now,
        )
        assert mode == PressureMode.CRITICAL

    def test_active_tighter_than_wall(self):
        now = datetime.now(timezone.utc)
        mode = compute_pressure_mode(
            deadline_at=now + timedelta(seconds=1150),  # wall near full
            max_wall_time_seconds=1200,
            active_runtime_ms=580_000,  # almost exhausted
            max_active_runtime_seconds=600,
            remaining_tokens=80_000,
            max_total_tokens=100_000,
            now=now,
        )
        assert mode == PressureMode.CRITICAL  # active takes precedence

    def test_token_tense_escalates(self):
        now = datetime.now(timezone.utc)
        mode = compute_pressure_mode(
            deadline_at=now + timedelta(seconds=1150),
            max_wall_time_seconds=1200,
            active_runtime_ms=100_000,
            max_active_runtime_seconds=600,
            remaining_tokens=10_000,  # 10%
            max_total_tokens=100_000,
            now=now,
        )
        assert mode == PressureMode.CONSERVATIVE  # token escalates from NORMAL to CONSERVATIVE

    def test_unknown_deadline(self):
        now = datetime.now(timezone.utc)
        mode = compute_pressure_mode(
            deadline_at=None,
            max_wall_time_seconds=1200,
            active_runtime_ms=100_000,
            max_active_runtime_seconds=600,
            remaining_tokens=80_000,
            max_total_tokens=100_000,
            now=now,
        )
        assert mode == PressureMode.NORMAL

    def test_approval_waiting_does_not_escalate_active(self):
        """active_runtime_ms 不变 = 审批等待不计入，不应从 NORMAL 跳 CRITICAL。"""
        now = datetime.now(timezone.utc)
        mode = compute_pressure_mode(
            deadline_at=now + timedelta(seconds=100),  # wall tight
            max_wall_time_seconds=1200,
            active_runtime_ms=200_000,  # active still plenty
            max_active_runtime_seconds=600,
            remaining_tokens=80_000,
            max_total_tokens=100_000,
            now=now,
        )
        # wall is tight (100/1200 ~8%) → critical; but active is fine → active says normal
        # tighter wins, so we get critical from wall
        assert mode == PressureMode.CRITICAL
        # Now show that if wall is fine, active being fine → NORMAL
        mode2 = compute_pressure_mode(
            deadline_at=now + timedelta(seconds=1000),
            max_wall_time_seconds=1200,
            active_runtime_ms=200_000,
            max_active_runtime_seconds=600,
            remaining_tokens=80_000,
            max_total_tokens=100_000,
            now=now,
        )
        assert mode2 == PressureMode.NORMAL
