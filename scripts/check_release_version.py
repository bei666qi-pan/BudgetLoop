#!/usr/bin/env python3
"""Fail when a BudgetLoop release surface drifts from the root VERSION."""

from __future__ import annotations

import json
import os
import plistlib
import sys
import tomllib
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


def read_json(path: str) -> dict[str, Any]:
    return json.loads((ROOT / path).read_text())


def read_toml(path: str) -> dict[str, Any]:
    with (ROOT / path).open("rb") as file:
        return tomllib.load(file)


def main() -> int:
    version = (ROOT / "VERSION").read_text().strip()
    expected = {
        "web/package.json": read_json("web/package.json")["version"],
        "web/package-lock.json": read_json("web/package-lock.json")["version"],
        "web/package-lock.json root package": read_json("web/package-lock.json")["packages"][""][
            "version"
        ],
        "backend/pyproject.toml": read_toml("backend/pyproject.toml")["project"]["version"],
        "desktop/windows/package.json": read_json("desktop/windows/package.json")["version"],
        "desktop/windows/package-lock.json": read_json("desktop/windows/package-lock.json")[
            "version"
        ],
        "desktop/windows/package-lock.json root package": read_json(
            "desktop/windows/package-lock.json"
        )["packages"][""]["version"],
        "desktop/windows/src-tauri/Cargo.toml": read_toml(
            "desktop/windows/src-tauri/Cargo.toml"
        )["package"]["version"],
        "desktop/windows/src-tauri/tauri.conf.json": read_json(
            "desktop/windows/src-tauri/tauri.conf.json"
        )["version"],
    }

    with (ROOT / "desktop/Info.plist").open("rb") as file:
        info = plistlib.load(file)
    expected["desktop/Info.plist short version"] = info["CFBundleShortVersionString"]
    expected["desktop/Info.plist bundle version"] = info["CFBundleVersion"]

    cargo_lock = read_toml("desktop/windows/src-tauri/Cargo.lock")
    windows_package = next(
        package
        for package in cargo_lock["package"]
        if package["name"] == "budgetloop-windows-launcher"
    )
    expected["desktop/windows/src-tauri/Cargo.lock"] = windows_package["version"]

    errors = [f"{name}: {value!r}" for name, value in expected.items() if value != version]

    release_notes = ROOT / "docs" / "releases" / f"v{version}.md"
    if not release_notes.is_file():
        errors.append(f"missing release notes: {release_notes.relative_to(ROOT)}")

    for readme in ("README.md", "README.zh-CN.md"):
        text = (ROOT / readme).read_text()
        if f"v{version}" not in text:
            errors.append(f"{readme}: missing v{version}")

    ref_type = os.getenv("GITHUB_REF_TYPE")
    ref_name = os.getenv("GITHUB_REF_NAME")
    if ref_type == "tag" and ref_name != f"v{version}":
        errors.append(f"Git tag {ref_name!r} does not match v{version}")

    if errors:
        print(f"Release version mismatch; VERSION declares {version}:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    print(f"All BudgetLoop release surfaces match v{version}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
