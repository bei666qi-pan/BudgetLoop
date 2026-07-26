"""全局配置：仅从环境变量读取，密钥绝不入库、不进前端、不进日志。"""
from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql://budgetloop:budgetloop@localhost:5432/budgetloop"
    redis_url: str = "redis://localhost:6379/0"
    api_token: str = "budgetloop-dev-token"

    litellm_base_url: str = "http://localhost:4000"
    litellm_master_key: str = ""

    # 可替换 AI API 网关。空 type 允许旧部署由 LITELLM_* 自动解析。
    ai_gateway_type: str = ""
    ai_gateway_base_url: str = ""
    ai_gateway_api_key: str = ""
    ai_gateway_console_url: str = ""
    ai_gateway_recommendation_model: str = ""
    ai_gateway_default_model: str = ""
    ai_gateway_deployment_label: str = ""
    ai_gateway_network_label: str = ""
    ai_gateway_reasoning_effort: str = ""
    ai_gateway_thinking_enabled: bool = False
    ai_gateway_thinking_budget_tokens: int = Field(default=0, ge=0, le=65_536)
    ai_recommendation_enabled: bool = True
    ai_gateway_connect_timeout_seconds: float = Field(default=2.0, ge=0.2, le=10.0)
    ai_gateway_read_timeout_seconds: float = Field(default=8.0, ge=0.5, le=30.0)
    ai_gateway_status_ttl_seconds: float = Field(default=15.0, ge=0.0, le=300.0)
    ai_gateway_max_response_bytes: int = Field(default=20_000, ge=1_024, le=100_000)
    managed_ai_runtime_enabled: bool = True
    managed_ai_runtime_base_url: str = "http://127.0.0.1:8000/api/runtime/ai/v1"
    managed_ai_runtime_container_base_url: str = (
        "http://host.docker.internal:8000/api/runtime/ai/v1"
    )
    managed_ai_runtime_token_ttl_seconds: int = Field(default=43_200, ge=300, le=86_400)
    managed_ai_runtime_max_request_bytes: int = Field(default=100_000, ge=1_024, le=1_000_000)
    managed_ai_runtime_est_tokens: int = Field(default=4_096, ge=256, le=65_536)
    managed_ai_runtime_est_cost: float = Field(default=0.0, ge=0.0, le=100.0)

    agent_server_image: str = "ghcr.io/openhands/agent-server:latest-python"
    # Docker-published agent-server ports are reached from the worker.  The
    # compose worker runs in a container, so Docker Desktop exposes those
    # ports via host.docker.internal rather than the worker's loopback.
    workspace_published_host: str = ""
    enable_cli_engines: bool = False
    cli_workspace_root: str = "./workspaces/cli"
    cli_engine_state_root: str = "./workspaces/engine-state"

    artifact_backend: str = "local"  # local | minio
    artifact_local_dir: str = "./artifacts"
    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = ""
    minio_bucket: str = "budgetloop-artifacts"

    # worker 心跳与 sweeper
    worker_heartbeat_ttl_seconds: int = 120
    sweeper_interval_seconds: int = 5

    # 输出截断（大段日志/模型内容大小限制）
    summary_max_chars: int = 2000
    artifact_max_bytes: int = 5 * 1024 * 1024
    project_upload_max_files: int = Field(default=2_000, ge=1, le=10_000)
    project_upload_max_file_bytes: int = Field(
        default=10 * 1024 * 1024, ge=1_024, le=100 * 1024 * 1024
    )
    project_upload_max_total_bytes: int = Field(
        default=100 * 1024 * 1024, ge=1_024, le=1024 * 1024 * 1024
    )


settings = Settings()
