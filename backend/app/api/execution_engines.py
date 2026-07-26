"""Execution engine source, capability and runtime availability API."""

from fastapi import APIRouter

from app.execution_engines import DEFAULT_ENGINE_ID, list_engines

router = APIRouter(tags=["execution-engines"])


@router.get("/execution-engines")
def get_execution_engines() -> dict:
    return {
        "default_engine": DEFAULT_ENGINE_ID,
        "engines": list_engines(),
        "authority": {
            "control_plane": "BudgetLoop",
            "durable_state": "PostgreSQL",
            "engines_are_replaceable": True,
            "silent_fallback": False,
        },
    }
