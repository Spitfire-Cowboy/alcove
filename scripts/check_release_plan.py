#!/usr/bin/env python3
"""Validate public-safe 0.4.0 release docs before tagging."""

from __future__ import annotations

import re
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
PLAN_PATH = REPO_ROOT / "docs" / "RELEASE_0_4_0_PLAN.md"
CHANGELOG_PATH = REPO_ROOT / "CHANGELOG.md"
ROADMAP_PATH = REPO_ROOT / "docs" / "ROADMAP.md"
PYPROJECT_PATH = REPO_ROOT / "pyproject.toml"
INIT_PATH = REPO_ROOT / "alcove" / "__init__.py"

PUBLIC_DOCS = [
    CHANGELOG_PATH,
    ROADMAP_PATH,
    PLAN_PATH,
    REPO_ROOT / "docs" / "RELEASE_CHECKLIST.md",
]

BANNED_MARKERS = [
    "/Users/",
    "alcove-private",
    "rowan-den",
    "Pro777",
]


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _project_version() -> str:
    match = re.search(
        r'^\[project\][\s\S]*?^version = "([^"]+)"$',
        _read(PYPROJECT_PATH),
        re.MULTILINE,
    )
    if not match:
        return ""
    return match.group(1)


def _package_version() -> str:
    match = re.search(r'^__version__ = "([^"]+)"$', _read(INIT_PATH), re.MULTILINE)
    if not match:
        return ""
    return match.group(1)


def validate() -> list[str]:
    errors: list[str] = []

    for path in (PLAN_PATH, CHANGELOG_PATH, ROADMAP_PATH, PYPROJECT_PATH, INIT_PATH):
        if not path.exists():
            errors.append(f"missing required file: {path.relative_to(REPO_ROOT)}")

    if errors:
        return errors

    package_version = _project_version()
    if package_version != "0.4.0":
        errors.append("0.4.0 release branch should set package version to 0.4.0")
    if _package_version() != package_version:
        errors.append("alcove.__version__ must match pyproject.toml")

    plan = _read(PLAN_PATH)
    changelog = _read(CHANGELOG_PATH)
    roadmap = _read(ROADMAP_PATH)

    required_plan_markers = [
        "Status: release-prep complete.",
        "Target tag: `v0.4.0`.",
        "Current package version: 0.4.0.",
        "## Release Scope",
        "## Release Checklist",
    ]
    for marker in required_plan_markers:
        if marker not in plan:
            errors.append(f"release notes missing marker: {marker}")

    if not re.search(r"^## \[0\.4\.0\] - 2026-05-12$", changelog, re.MULTILINE):
        errors.append("CHANGELOG.md must include the dated 0.4.0 release entry")
    if "Current package release (v0.4.0)" not in roadmap:
        errors.append("docs/ROADMAP.md must describe 0.4.0 as the current package release")
    if "planning only" in plan or "not released, not tagged" in changelog:
        errors.append("0.4.0 release docs must not use planning-only language")

    for path in PUBLIC_DOCS:
        text = _read(path)
        for marker in BANNED_MARKERS:
            if marker in text:
                errors.append(
                    f"{path.relative_to(REPO_ROOT)} contains private marker {marker!r}"
                )

    return errors


def main() -> int:
    errors = validate()
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1

    print("0.4.0 release checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
