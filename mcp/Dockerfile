FROM python:3.12-slim

WORKDIR /srv
COPY pyproject.toml server.py ./

RUN pip install --no-cache-dir .

# SSE 模式：Agent 通过 HTTP 连接
EXPOSE 3100

CMD ["budgetloop-mcp", "--transport", "sse", "--host", "0.0.0.0", "--port", "3100"]
