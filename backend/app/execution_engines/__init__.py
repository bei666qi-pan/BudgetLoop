"""Replaceable execution engines governed by the BudgetLoop control plane."""

from app.execution_engines.adapters import adapter_for
from app.execution_engines.registry import (
    DEFAULT_ENGINE_ID,
    ENGINES,
    engine_preflight,
    get_engine,
    list_engines,
)

__all__ = [
    "DEFAULT_ENGINE_ID",
    "ENGINES",
    "adapter_for",
    "engine_preflight",
    "get_engine",
    "list_engines",
]
