from __future__ import annotations

import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def _read(rel_path: str) -> str:
    return (REPO_ROOT / rel_path).read_text(encoding="utf-8")


def test_release_checklist_exists_and_has_core_sections() -> None:
    path = REPO_ROOT / "docs" / "RELEASE_CHECKLIST.md"
    assert path.exists(), f"Missing release checklist: {path}"
    text = path.read_text(encoding="utf-8")
    for section in ("## Pre-release", "## Release", "## Post-release"):
        assert section in text
    assert ".github/workflows/release.yml" in text
    assert ".github/workflows/publish.yml" in text
    assert "RELEASE_0_4_0_PLAN.md" in text


def test_release_0_4_0_plan_is_planning_only() -> None:
    plan = _read("docs/RELEASE_0_4_0_PLAN.md")
    changelog = _read("CHANGELOG.md")
    roadmap = _read("docs/ROADMAP.md")
    pyproject = _read("pyproject.toml")

    assert "Status: planning only." in plan
    assert "Target: 0.4.0 feature-batch release." in plan
    assert "## PR Review Sequence" in plan
    assert "not as 0.4.0 features" in plan
    assert "## [0.4.0] - Planned" in changelog
    assert "not released, not tagged" in changelog
    assert "Next release planning (0.4.0)" in roadmap
    assert 'version = "0.3.0"' in pyproject
    assert 'version = "1.0.0"' not in pyproject


def test_release_plan_checker_passes() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/check_release_plan.py"],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "release plan checks passed" in result.stdout


def test_canonical_public_repo_slug_in_metadata_and_docs() -> None:
    expected_markers = {
        "README.md": "Spitfire-Cowboy/alcove",
        "docs/SECURITY.md": "Spitfire-Cowboy/alcove",
        "docs/index.html": "Spitfire-Cowboy/alcove",
        "pyproject.toml": "Spitfire-Cowboy/alcove",
        ".github/workflows/publish.yml": "owner=Spitfire-Cowboy, repo=alcove",
        "scripts/release.sh": "Spitfire-Cowboy/alcove",
    }
    for rel, marker in expected_markers.items():
        text = _read(rel)
        assert marker in text, f"Missing canonical marker in {rel}"
        assert "Pro777/alcove" not in text, f"Legacy slug found in {rel}"


def test_demo_links_use_current_pages_domain() -> None:
    files = [
        "README.md",
        "docs/index.html",
        "alcove/web/templates/search.html",
    ]
    for rel in files:
        text = _read(rel)
        assert "pro777.github.io/alcove" not in text, f"Legacy Pages domain found in {rel}"
        assert "spitfire-cowboy.github.io/alcove" in text, (
            f"Missing canonical Pages domain in {rel}"
        )


def test_public_docs_avoid_private_operational_markers() -> None:
    files = [
        "README.md",
        "CHANGELOG.md",
        "docs/ROADMAP.md",
        "docs/RELEASE_0_4_0_PLAN.md",
        "docs/RELEASE_CHECKLIST.md",
        "docs/SECURITY.md",
        "docs/index.html",
        "docs/demo-cli.html",
    ]
    banned = ["alcove-private", "rowan-den", "/Users/", "Pro777"]
    for rel in files:
        text = _read(rel)
        for marker in banned:
            assert marker not in text, f"Found private marker {marker!r} in {rel}"
