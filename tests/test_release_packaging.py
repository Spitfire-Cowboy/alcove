from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "check_release_packaging.py"


def _load_release_packaging_module():
    spec = importlib.util.spec_from_file_location("check_release_packaging", SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_public_release_packaging_checks_pass() -> None:
    module = _load_release_packaging_module()

    checks = module.run_checks(REPO_ROOT)

    assert "package name is alcove-search" in checks
    assert "package license is Apache-2.0" in checks
    assert "release workflow exists" in checks
    assert "PyPI publish workflow exists" in checks


def test_unsafe_homebrew_formula_is_rejected(tmp_path: Path) -> None:
    module = _load_release_packaging_module()
    formula_dir = tmp_path / "Formula"
    workflow_dir = tmp_path / ".github" / "workflows"
    formula_dir.mkdir(parents=True)
    workflow_dir.mkdir(parents=True)
    (workflow_dir / "release.yml").write_text("name: release\n", encoding="utf-8")
    (workflow_dir / "publish.yml").write_text("name: publish\n", encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text(
        '\n'.join(
            [
                '[project]',
                'name = "alcove-search"',
                'version = "0.4.0"',
                'license = {text = "Apache-2.0"}',
                '',
                '[project.urls]',
                'Homepage = "https://spitfire-cowboy.github.io/alcove/"',
                'Repository = "https://github.com/Spitfire-Cowboy/alcove"',
                '',
                '[project.scripts]',
                'alcove = "alcove.cli:main"',
            ]
        ),
        encoding="utf-8",
    )
    (formula_dir / "alcove.rb").write_text(
        '\n'.join(
            [
                "class Alcove < Formula",
                '  homepage "https://example.invalid/internal/alcove"',
                '  url "https://files.pythonhosted.org/packages/source/a/alcove-search/alcove_search-0.1.0.tar.gz"',
                '  sha256 "REPLACE_WITH_RELEASE_SHA256"',
                '  license "MIT"',
                "end",
            ]
        ),
        encoding="utf-8",
    )

    with pytest.raises(AssertionError, match=r"Formula/alcove\.rb is not release-safe"):
        module.run_checks(tmp_path)
