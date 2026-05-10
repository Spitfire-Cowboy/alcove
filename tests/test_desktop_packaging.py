from __future__ import annotations

import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
PYPROJECT = REPO_ROOT / "pyproject.toml"
DESKTOP_DOC = REPO_ROOT / "docs" / "DESKTOP.md"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_briefcase_metadata_is_public_and_preparatory_only() -> None:
    text = _read(PYPROJECT)

    assert '[tool.briefcase]' in text
    assert 'bundle = "com.alcove-search"' in text
    assert 'url = "https://github.com/Spitfire-Cowboy/alcove"' in text

    app_target = re.search(r"^\[tool\.briefcase\.app\.[^\]]+\]", text, re.MULTILINE)
    assert app_target is None, (
        "Do not add a Briefcase app target until docs/DESKTOP.md prerequisites are met"
    )


def test_desktop_packaging_doc_is_honest_about_status() -> None:
    text = _read(DESKTOP_DOC)

    required = [
        "does not currently ship a desktop application bundle",
        "packaging preparation only",
        "briefcase build",
        "not supported release paths",
        "Until then, the honest state is preparation",
    ]
    for phrase in required:
        assert phrase in text


def test_desktop_packaging_preserves_local_first_boundary() -> None:
    text = _read(DESKTOP_DOC)

    required = [
        "stay on the operator's disk",
        "must not add telemetry",
        "account creation",
        "hosted storage",
        "background network calls",
        "Sentence-transformers remains opt-in",
    ]
    for phrase in required:
        assert phrase in text


def test_desktop_packaging_docs_are_public_safe() -> None:
    files = [
        PYPROJECT,
        DESKTOP_DOC,
        REPO_ROOT / "docs" / "ROADMAP.md",
        REPO_ROOT / "CHANGELOG.md",
    ]
    banned = [
        "/Users/",
        "alcove-private",
        "rowan-den",
        "Pro777/alcove",
        "localhost.localdomain",
    ]

    for path in files:
        text = _read(path)
        for marker in banned:
            assert marker not in text, f"Found private marker {marker!r} in {path}"
