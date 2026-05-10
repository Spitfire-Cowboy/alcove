#!/usr/bin/env python3
"""Generate or validate the Homebrew formula scaffold.

This script deliberately refuses placeholder checksums. It is safe to keep the
template in-tree, but a generated formula should only be published after the
release artifact exists and its real SHA-256 has been verified.
"""

from __future__ import annotations

import argparse
import re
import sys
import tomllib
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TEMPLATE = REPO_ROOT / "packaging" / "homebrew" / "alcove-search.rb.template"
PRIVATE_REPO_RE = re.compile(r"github\.com/(?!Spitfire-Cowboy/alcove\b)[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+")
LOCAL_HOME_PATH_RE = re.compile(r"/(?:Users|home)/[A-Za-z0-9_.-]+")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
VERSION_RE = re.compile(r"^\d+\.\d+\.\d+(?:[A-Za-z0-9_.+-]+)?$")


class FormulaError(ValueError):
    """Raised when formula input is not safe to publish."""


def project_version(pyproject_path: Path = REPO_ROOT / "pyproject.toml") -> str:
    with pyproject_path.open("rb") as handle:
        data = tomllib.load(handle)
    return str(data["project"]["version"])


def validate_version(version: str) -> None:
    if not VERSION_RE.fullmatch(version):
        raise FormulaError(f"invalid version: {version!r}")


def validate_sha256(sha256: str) -> str:
    normalized = sha256.strip().lower()
    if not SHA256_RE.fullmatch(normalized):
        raise FormulaError("sha256 must be exactly 64 lowercase or uppercase hex characters")
    if len(set(normalized)) == 1:
        raise FormulaError("sha256 appears to be a placeholder")
    return normalized


def validate_public_text(text: str) -> None:
    unresolved = re.findall(r"{{[A-Z0-9_]+}}", text)
    if unresolved:
        raise FormulaError(f"formula has unresolved template tokens: {', '.join(sorted(set(unresolved)))}")
    if PRIVATE_REPO_RE.search(text):
        raise FormulaError("formula contains a non-canonical GitHub repository URL")
    if LOCAL_HOME_PATH_RE.search(text):
        raise FormulaError("formula contains a local home-directory path")
    if re.search(r"sha256\s+\"(?:0{64}|f{64})\"", text, flags=re.IGNORECASE):
        raise FormulaError("formula contains a placeholder sha256")
    if "Spitfire-Cowboy/alcove" not in text and "alcove_search-" not in text:
        raise FormulaError("formula does not point at the public Alcove release artifact")


def render_formula(version: str, sha256: str, template_path: Path = DEFAULT_TEMPLATE) -> str:
    validate_version(version)
    safe_sha = validate_sha256(sha256)
    text = template_path.read_text(encoding="utf-8")
    rendered = text.replace("{{VERSION}}", version).replace("{{SHA256}}", safe_sha)
    validate_public_text(rendered)
    return rendered


def check_formula(path: Path) -> None:
    validate_public_text(path.read_text(encoding="utf-8"))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate or validate Alcove's Homebrew formula.")
    parser.add_argument("--template", type=Path, default=DEFAULT_TEMPLATE, help="Formula template path")
    parser.add_argument("--version", default=project_version(), help="Release version to embed")
    parser.add_argument("--sha256", help="Real SHA-256 of the released sdist")
    parser.add_argument("--output", type=Path, help="Write generated formula to this path")
    parser.add_argument("--check", type=Path, help="Validate an already generated formula")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        if args.check:
            check_formula(args.check)
            return 0
        if not args.sha256:
            raise FormulaError("--sha256 is required; use the real released sdist checksum")
        formula = render_formula(args.version, args.sha256, args.template)
        if args.output:
            args.output.write_text(formula, encoding="utf-8")
        else:
            sys.stdout.write(formula)
        return 0
    except FormulaError as exc:
        parser.error(str(exc))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
