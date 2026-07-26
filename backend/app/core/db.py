"""数据库会话与引擎（同步 SQLAlchemy + psycopg v3；worker 与 FastAPI 共用）。

选择同步驱动的原因：预算 CAS 预留必须短小、可预测地持有行锁，
同步事务语义更简单可靠；FastAPI 端通过 run_in_threadpool 调用。
"""
from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings


def _normalize(url: str) -> str:
    # 接受 postgresql:// 形式，统一走 psycopg v3 驱动
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url


engine = create_engine(_normalize(settings.database_url), pool_size=10, max_overflow=20, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


@contextmanager
def session_scope() -> Iterator[Session]:
    """事务上下文：正常结束 commit，异常 rollback。"""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_db() -> Iterator[Session]:
    """FastAPI Depends 用。"""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
