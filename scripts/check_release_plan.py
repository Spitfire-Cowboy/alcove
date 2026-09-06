#!/usr/bin/env python3
"""Validate the current public release docs before tagging."""

from __future__ import annotations

import re
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
CHANGELOG_PATH = REPO_ROOT / "CHANGELOG.md"
ROADMAP_PATH = REPO_ROOT / "docs" / "ROADMAP.md"
PYPROJECT_PATH = REPO_ROOT / "pyproject.toml"
INIT_PATH = REPO_ROOT / "alcove" / "__init__.py"

PUBLIC_DOCS = [
    CHANGELOG_PATH,
    ROADMAP_PATH,
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


def _plan_path(version: str) -> Path:
    return REPO_ROOT / "docs" / f"RELEASE_{version.replace('.', '_')}_PLAN.md"


def validate() -> list[str]:
    errors: list[str] = []

    package_version = _project_version()
    plan_path = _plan_path(package_version)
    for path in (plan_path, CHANGELOG_PATH, ROADMAP_PATH, PYPROJECT_PATH, INIT_PATH):
        if not path.exists():
            errors.append(f"missing required file: {path.relative_to(REPO_ROOT)}")

    if errors:
        return errors

    if not re.fullmatch(r"\d+\.\d+\.\d+", package_version):
        errors.append("project version must use X.Y.Z format")
    if _package_version() != package_version:
        errors.append("alcove.__version__ must match pyproject.toml")

    plan = _read(plan_path)
    changelog = _read(CHANGELOG_PATH)
    roadmap = _read(ROADMAP_PATH)

    required_plan_markers = [
        "Status: release-prep complete.",
        f"Target tag: `v{package_version}`.",
        f"Current package version: {package_version}.",
        "## Release Scope",
        "## Release Checklist",
    ]
    for marker in required_plan_markers:
        if marker not in plan:
            errors.append(f"release notes missing marker: {marker}")

    changelog_heading = rf"^## \[{re.escape(package_version)}\] - \d{{4}}-\d{{2}}-\d{{2}}$"
    if not re.search(changelog_heading, changelog, re.MULTILINE):
        errors.append(
            f"CHANGELOG.md must include a dated {package_version} release entry"
        )
    if f"Current package release (v{package_version})" not in roadmap:
        errors.append(
            "docs/ROADMAP.md must describe "
            f"{package_version} as the current package release"
        )
    if "planning only" in plan or "not released, not tagged" in changelog:
        errors.append(
            f"{package_version} release docs must not use planning-only language"
        )

    for path in [*PUBLIC_DOCS, plan_path]:
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

    print(f"{_project_version()} release checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
