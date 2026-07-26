"""RunStatus 状态机转换表的完备性/一致性校验（纯内存，无需 docker）。"""
from __future__ import annotations

from collections import deque

from app.core.enums import ALLOWED_TRANSITIONS, TERMINAL_STATUSES, RunStatus

EXPECTED_TERMINAL = {
    RunStatus.COMPLETED,
    RunStatus.PARTIAL_COMPLETED,
    RunStatus.FAILED,
    RunStatus.BUDGET_EXHAUSTED,
    RunStatus.CANCELLED,
}


def test_all_statuses_have_table_entry():
    assert set(ALLOWED_TRANSITIONS.keys()) == set(RunStatus)


def test_terminal_statuses_constant():
    assert set(TERMINAL_STATUSES) == EXPECTED_TERMINAL


def test_terminal_states_have_no_outgoing_edges():
    for status in TERMINAL_STATUSES:
        assert ALLOWED_TRANSITIONS[status] == frozenset(), f"{status} must be a sink"


def test_is_terminal_property_matches_constant():
    for status in RunStatus:
        assert status.is_terminal == (status in TERMINAL_STATUSES)


def test_all_targets_are_valid_statuses():
    for src, targets in ALLOWED_TRANSITIONS.items():
        for dst in targets:
            assert isinstance(dst, RunStatus)
            assert dst != src, f"{src} has self-loop"


def _reachable(src: RunStatus) -> set[RunStatus]:
    seen = {src}
    queue = deque([src])
    while queue:
        node = queue.popleft()
        for nxt in ALLOWED_TRANSITIONS[node]:
            if nxt not in seen:
                seen.add(nxt)
                queue.append(nxt)
    return seen


def test_every_nonterminal_can_reach_cancelled():
    for status in RunStatus:
        if not status.is_terminal:
            assert RunStatus.CANCELLED in _reachable(status), f"{status} cannot reach CANCELLED"


def test_every_nonterminal_can_reach_some_terminal():
    for status in RunStatus:
        if not status.is_terminal:
            assert _reachable(status) & TERMINAL_STATUSES, f"{status} cannot reach any terminal state"


def test_pending_is_entry_state():
    """PENDING 只能由表外创建，不允许任何状态转回 PENDING。"""
    for targets in ALLOWED_TRANSITIONS.values():
        assert RunStatus.PENDING not in targets
