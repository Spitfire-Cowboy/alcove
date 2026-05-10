#!/usr/bin/env python3
"""Validate public-safe release planning docs without creating release artifacts."""

from __future__ import annotations

import re
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
PLAN_PATH = REPO_ROOT / "docs" / "RELEASE_0_4_0_PLAN.md"
CHANGELOG_PATH = REPO_ROOT / "CHANGELOG.md"
ROADMAP_PATH = REPO_ROOT / "docs" / "ROADMAP.md"
PYPROJECT_PATH = REPO_ROOT / "pyproject.toml"

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


def validate() -> list[str]:
    errors: list[str] = []

    for path in (PLAN_PATH, CHANGELOG_PATH, ROADMAP_PATH, PYPROJECT_PATH):
        if not path.exists():
            errors.append(f"missing required file: {path.relative_to(REPO_ROOT)}")

    if errors:
        return errors

    package_version = _project_version()
    if package_version == "1.0.0":
        errors.append("package version must not be bumped to 1.0.0")
    if package_version != "0.3.0":
        errors.append(
            "planning branch should keep package version at 0.3.0 until release"
        )

    plan = _read(PLAN_PATH)
    changelog = _read(CHANGELOG_PATH)
    roadmap = _read(ROADMAP_PATH)

    required_plan_markers = [
        "Status: planning only.",
        "Target: 0.4.0 feature-batch release.",
        "Current package version: 0.3.0 until the release commit.",
        "## PR Review Sequence",
        "not as 0.4.0 features",
    ]
    for marker in required_plan_markers:
        if marker not in plan:
            errors.append(f"release plan missing marker: {marker}")

    if not re.search(r"^## \[0\.4\.0\] - Planned$", changelog, re.MULTILINE):
        errors.append("CHANGELOG.md must include a planned 0.4.0 entry")
    if "not released, not tagged" not in changelog:
        errors.append("CHANGELOG.md must state that 0.4.0 is not released")
    if "0.4.0" not in roadmap:
        errors.append("docs/ROADMAP.md must reference the 0.4.0 planning target")

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

    print("release plan checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
