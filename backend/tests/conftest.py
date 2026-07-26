"""测试基础设施：testcontainers PostgreSQL + 独立事务回滚的 pg_session fixture。"""
from __future__ import annotations

import shutil

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.core.models import Base

DOCKER_AVAILABLE = shutil.which("docker") is not None
requires_docker = pytest.mark.skipif(not DOCKER_AVAILABLE, reason="docker not available")


def _normalize(url: str) -> str:
    if url.startswith("postgresql+psycopg2://"):
        # testcontainers 默认返回 psycopg2 方言 URL；本项目依赖 psycopg v3
        return url.replace("postgresql+psycopg2://", "postgresql+psycopg://", 1)
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url


@pytest.fixture(scope="session")
def pg_url() -> str:
    """session 级 testcontainers PG；docker 不可用则 skip。"""
    if not DOCKER_AVAILABLE:
        pytest.skip("docker not available")
    try:
        from testcontainers.postgres import PostgresContainer
    except ImportError:
        pytest.skip("testcontainers[postgres] not installed")
    try:
        container = PostgresContainer("postgres:16-alpine")
        container.start()
    except Exception as exc:
        pytest.skip(f"cannot start postgres container: {exc}")
    with container:
        yield container.get_connection_url()


@pytest.fixture()
def pg_engine(pg_url):
    engine = create_engine(_normalize(pg_url))
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture()
def pg_session(pg_engine) -> Session:
    """绑定到外层事务的 Session：测试结束整体回滚，不污染共享容器。"""
    connection = pg_engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection, expire_on_commit=False)
    yield session
    session.close()
    transaction.rollback()
    connection.close()
