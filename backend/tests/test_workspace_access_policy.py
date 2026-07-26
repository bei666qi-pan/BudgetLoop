from __future__ import annotations

import os

import pytest

from app.policy.workspace_access import normalize_project_dir, validate_workspace_access


def test_project_dir_normalizes_without_broadening_scope() -> None:
    assert normalize_project_dir("  /tmp/budgetloop-project/  ") == "/tmp/budgetloop-project"
    assert normalize_project_dir("") is None
    assert normalize_project_dir(None) is None


@pytest.mark.parametrize(
    "path",
    ["relative/project", "/", "/etc", "/private/tmp/project", "/tmp/../etc"],
)
def test_project_dir_rejects_non_canonical_or_sensitive_roots(path: str) -> None:
    with pytest.raises(ValueError):
        normalize_project_dir(path)


def test_project_dir_rejects_home_but_allows_a_child() -> None:
    home = os.path.expanduser("~")
    with pytest.raises(ValueError, match="home directory"):
        normalize_project_dir(home)
    assert normalize_project_dir(f"{home}/project") == f"{home}/project"


def test_full_access_requires_a_project_but_isolated_does_not() -> None:
    validate_workspace_access("isolated", None)
    with pytest.raises(ValueError, match="project_dir"):
        validate_workspace_access("full_access", None)
    validate_workspace_access("full_access", "/tmp/project")
