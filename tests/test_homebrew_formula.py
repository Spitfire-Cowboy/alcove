from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "generate_homebrew_formula.py"
REALISTIC_SHA = "2a9f3c4d5e6b718293a4b5c6d7e8f90123456789abcdef0123456789abcd1234"


def _load_generator():
    spec = importlib.util.spec_from_file_location("generate_homebrew_formula", SCRIPT_PATH)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_generator_requires_real_sha256() -> None:
    generator = _load_generator()

    with pytest.raises(generator.FormulaError):
        generator.render_formula("0.3.0", "0" * 64)

    with pytest.raises(generator.FormulaError):
        generator.render_formula("0.3.0", "not-a-sha")


def test_generator_renders_public_formula_without_unresolved_tokens() -> None:
    generator = _load_generator()

    formula = generator.render_formula("0.3.0", REALISTIC_SHA.upper())

    assert "{{" not in formula
    assert "}}" not in formula
    assert 'sha256 "2a9f3c4d5e6b718293a4b5c6d7e8f90123456789abcdef0123456789abcd1234"' in formula
    assert "alcove_search-0.3.0.tar.gz" in formula
    assert "github.com/example/private" not in formula
    assert "/home/example" not in formula


def test_formula_check_rejects_unresolved_template_tokens(tmp_path: Path) -> None:
    generator = _load_generator()
    formula = tmp_path / "alcove-search.rb"
    formula.write_text(
        'url "https://files.pythonhosted.org/packages/source/a/alcove-search/alcove_search-{{VERSION}}.tar.gz"\n'
        'sha256 "{{SHA256}}"\n',
        encoding="utf-8",
    )

    with pytest.raises(generator.FormulaError):
        generator.check_formula(formula)


def test_formula_check_rejects_private_repo_and_local_paths(tmp_path: Path) -> None:
    generator = _load_generator()

    formula = tmp_path / "alcove-search.rb"
    formula.write_text(
        'homepage "https://github.com/example/private"\n'
        'url "file:///home/example/alcove_search-0.3.0.tar.gz"\n'
        f'sha256 "{REALISTIC_SHA}"\n',
        encoding="utf-8",
    )

    with pytest.raises(generator.FormulaError):
        generator.check_formula(formula)
