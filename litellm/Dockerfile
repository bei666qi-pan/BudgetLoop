# BudgetLoop LiteLLM 网关镜像
#
# 生产建议：main-stable 是滚动 tag，升级会悄悄带入行为变化。
# 正式上线前应 pin 到具体 release（例如 ghcr.io/berriai/litellm-database:v1.xx.x），
# 并在升级前跑一遍预算拦截回归（预算拒绝、settle/release 正确性）。
FROM ghcr.io/berriai/litellm-database:main-stable

# 自定义预算回调（budget_callback.py）需要直连业务 PostgreSQL。
# psycopg v3，binary 包免编译，适合 slim 基础镜像。
RUN pip install --no-cache-dir "psycopg[binary]"

COPY config.yaml /app/config.yaml
COPY budget_callback.py /app/budget_callback.py

# 基础镜像 ENTRYPOINT 为 litellm，此处仅传启动参数。
# 自定义回调文件必须与 config.yaml 同目录（/app），LiteLLM 按
# config.yaml 所在目录解析 litellm_settings.callbacks 中的 python 模块名。
CMD ["--config", "/app/config.yaml", "--port", "4000"]
