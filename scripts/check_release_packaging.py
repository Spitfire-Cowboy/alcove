#!/usr/bin/env python3
from __future__ import annotations

import re
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]

BANNED_MARKERS = ("/Users/",)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _project_version(pyproject_text: str) -> str:
    match = re.search(r'^version = "([^"]+)"$', pyproject_text, re.MULTILINE)
    if not match:
        raise AssertionError("pyproject.toml is missing project version")
    return match.group(1)


def check_pyproject(root: Path = REPO_ROOT) -> list[str]:
    text = _read(root / "pyproject.toml")
    checks = {
        'name = "alcove-search"': "package name is alcove-search",
        'license = {text = "Apache-2.0"}': "package license is Apache-2.0",
        'Repository = "https://github.com/Spitfire-Cowboy/alcove"': (
            "repository URL is public"
        ),
        'Homepage = "https://spitfire-cowboy.github.io/alcove/"': (
            "homepage URL is public docs site"
        ),
        'alcove = "alcove.cli:main"': "CLI entry point is declared",
    }
    missing = [description for marker, description in checks.items() if marker not in text]
    if missing:
        raise AssertionError("pyproject.toml failed checks: " + ", ".join(missing))
    return list(checks.values())


def check_release_workflows(root: Path = REPO_ROOT) -> list[str]:
    required = [
        root / ".github" / "workflows" / "release.yml",
        root / ".github" / "workflows" / "publish.yml",
    ]
    missing = [str(path.relative_to(root)) for path in required if not path.exists()]
    if missing:
        raise AssertionError("missing release workflow(s): " + ", ".join(missing))
    return ["release workflow exists", "PyPI publish workflow exists"]


def check_homebrew_formula(root: Path = REPO_ROOT) -> list[str]:
    formula = root / "Formula" / "alcove.rb"
    if not formula.exists():
        return ["no Homebrew formula present; public release path is PyPI-only"]

    formula_text = _read(formula)
    pyproject_text = _read(root / "pyproject.toml")
    version = _project_version(pyproject_text)
    expected_sdist = f"alcove_search-{version}.tar.gz"
    required = {
        'homepage "https://github.com/Spitfire-Cowboy/alcove"': (
            "Homebrew homepage is public repo"
        ),
        'license "Apache-2.0"': "Homebrew license matches package metadata",
        expected_sdist: "Homebrew sdist URL matches pyproject version",
    }

    failures = [
        description for marker, description in required.items() if marker not in formula_text
    ]
    banned_hits = [marker for marker in BANNED_MARKERS if marker in formula_text]
    if "REPLACE_WITH_RELEASE_SHA256" in formula_text:
        banned_hits.append("REPLACE_WITH_RELEASE_SHA256")
    if re.search(r'sha256 "[0-9a-f]{64}"', formula_text) is None:
        failures.append("Homebrew formula has a real sha256")

    if failures or banned_hits:
        details = []
        if failures:
            details.append("failed checks: " + ", ".join(failures))
        if banned_hits:
            details.append("blocked marker(s): " + ", ".join(banned_hits))
        raise AssertionError("Formula/alcove.rb is not release-safe: " + "; ".join(details))

    return list(required.values()) + ["Homebrew formula has a real sha256"]


def run_checks(root: Path = REPO_ROOT) -> list[str]:
    checks: list[str] = []
    checks.extend(check_pyproject(root))
    checks.extend(check_release_workflows(root))
    checks.extend(check_homebrew_formula(root))
    return checks


def main() -> int:
    try:
        checks = run_checks()
    except AssertionError as exc:
        print(f"release packaging check failed: {exc}", file=sys.stderr)
        return 1

    for check in checks:
        print(f"ok: {check}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
