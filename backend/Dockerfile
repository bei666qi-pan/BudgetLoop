# syntax=docker/dockerfile:1.7
ARG CODEX_CLI_VERSION=0.145.0
ARG GEMINI_CLI_VERSION=0.52.0
ARG NODE_VERSION=22.20.0
ARG PYTHON_IMAGE=docker.1ms.run/library/python:3.12-slim

FROM ${PYTHON_IMAGE}
ARG TARGETARCH
ARG NODE_VERSION
ARG CODEX_CLI_VERSION
ARG GEMINI_CLI_VERSION

# Install the official fixed Node distribution with architecture-specific
# checksums. This avoids a second large base-image pull while remaining
# reproducible on Apple Silicon and x86_64 builders.
RUN --mount=type=cache,target=/tmp/node-downloads \
    TARGETARCH="${TARGETARCH:-arm64}" NODE_VERSION="${NODE_VERSION}" python - <<'PY'
import hashlib
import os
import shutil
import tarfile
import urllib.request
from pathlib import Path

architecture = {"arm64": "arm64", "amd64": "x64"}.get(os.environ["TARGETARCH"])
if architecture is None:
    raise SystemExit(f"unsupported Node architecture: {os.environ['TARGETARCH']}")
checksums = {
    "arm64": "06907b9c088ce62305bc1530e5c1ae1510245114645768f7750c349c5b6fe667",
    "x64": "00bbd05e306ea68b6e13e17360d0e2f680b493ef95f2fea1c4296ff7437530bc",
}
version = os.environ["NODE_VERSION"]
archive = Path(f"/tmp/node-downloads/node-v{version}-linux-{architecture}.tar.xz")
if not archive.exists():
    urllib.request.urlretrieve(
        f"https://registry.npmmirror.com/-/binary/node/v{version}/{archive.name}",
        archive,
    )
if hashlib.sha256(archive.read_bytes()).hexdigest() != checksums[architecture]:
    raise SystemExit("Node distribution checksum mismatch")
root = Path("/tmp/node-extract")
shutil.rmtree(root, ignore_errors=True)
with tarfile.open(archive) as bundle:
    bundle.extractall(root, filter="data")
source = root / f"node-v{version}-linux-{architecture}"
for item in source.iterdir():
    target = Path("/usr/local") / item.name
    if item.is_dir():
        shutil.copytree(item, target, dirs_exist_ok=True, symlinks=True)
    else:
        shutil.copy2(item, target)
PY
RUN --mount=type=cache,target=/root/.npm \
    npm config set registry https://registry.npmmirror.com \
    && npm install --global --omit=dev \
      "@openai/codex@${CODEX_CLI_VERSION}" \
      "@google/gemini-cli@${GEMINI_CLI_VERSION}" \
    && codex --version \
    && gemini --version
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates git \
    && rm -rf /var/lib/apt/lists/* \
    && git --version

WORKDIR /srv

COPY pyproject.toml ./
COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./

# Keep PyPI wheels in a BuildKit cache and tolerate transient TLS reads.  This
# makes a normal local rebuild resilient without baking credentials or proxy
# settings into the image.
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --index-url https://pypi.tuna.tsinghua.edu.cn/simple \
      --retries 5 --timeout 120 .

# 默认命令由 docker-compose 覆盖（uvicorn / dramatiq）
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
