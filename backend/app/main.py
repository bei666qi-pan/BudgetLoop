"""BudgetLoop Control Plane FastAPI 应用入口。

启动时执行 alembic upgrade head（SKIP_MIGRATIONS=1 可跳过，如测试场景）；
迁移失败则启动失败并打日志——绝不在漂移的 schema 上提供服务。
"""
from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import (
    ai_gateway,
    approvals,
    execution_engines,
    observations,
    project_uploads,
    runs,
    runtime_ai,
    stream,
    task_drafts,
    tasks,
    team_presets,
    work_containers,
)
from app.core.security import require_token

logger = logging.getLogger(__name__)

_BACKEND_DIR = Path(__file__).resolve().parent.parent


def run_migrations() -> None:
    """用 alembic Python API 升级到 head。失败抛异常阻断启动。"""
    from alembic.config import Config

    from alembic import command

    cfg = Config(str(_BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(_BACKEND_DIR / "alembic"))
    command.upgrade(cfg, "head")


@asynccontextmanager
async def lifespan(app: FastAPI):
    if os.environ.get("SKIP_MIGRATIONS") == "1":
        logger.info("SKIP_MIGRATIONS=1, skipping alembic upgrade")
    else:
        try:
            run_migrations()
            logger.info("database migrations up to date")
        except Exception:
            logger.exception("alembic upgrade head failed; refusing to start")
            raise
    yield


app = FastAPI(title="BudgetLoop Control Plane", lifespan=lifespan)

# web 前端开发端口（vite 5173 / next 3000）
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Generated applications authenticate with a short-lived run-scoped capability,
# not the operator API token used by the normal secured router set.
app.include_router(runtime_ai.router, prefix="/api")


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


_secured = [Depends(require_token)]
for router in (
    ai_gateway.router,
    task_drafts.router,
    tasks.router,
    runs.router,
    observations.router,
    project_uploads.router,
    approvals.router,
    stream.router,
    execution_engines.router,
    team_presets.router,
    work_containers.router,
):
    app.include_router(router, prefix="/api", dependencies=_secured)
