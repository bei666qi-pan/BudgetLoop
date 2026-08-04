"""导出 BudgetLoop OpenAPI spec 为静态 JSON 文件。

用法: python -m app.client.export_openapi > docs/openapi.json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# 添加 backend 到 sys.path
_backend = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_backend))

from app.main import app  # noqa: E402


def main() -> None:
    spec = app.openapi()
    print(json.dumps(spec, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
