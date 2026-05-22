from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


_SCRIPT = Path(__file__).parent.parent / "scripts" / "check_dependency_integrity.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("check_dependency_integrity", _SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules["check_dependency_integrity"] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


_mod = _load_module()


def test_load_constraints_ignores_comments_and_blanks(tmp_path):
    path = tmp_path / "constraints.txt"
    path.write_text("# comment\n\nfastapi>=0.115.0,<1.0\n", encoding="utf-8")

    assert _mod.load_constraints(path) == ["fastapi>=0.115.0,<1.0"]


def test_normalize_requirement_equates_reordered_specifiers():
    left = "FastAPI <1.0, >=0.115.0"
    right = "fastapi>=0.115.0,<1.0"

    assert _mod.normalize_requirement(left) == _mod.normalize_requirement(right)


def test_evaluate_requirement_reports_invalid_requirement():
    result = _mod.evaluate_requirement("not a valid requirement >>>")

    assert result.status == "invalid-requirement"
    assert result.installed is None


def test_evaluate_requirement_reports_missing_package(monkeypatch):
    monkeypatch.setattr(
        _mod.importlib_metadata,
        "version",
        lambda name: (_ for _ in ()).throw(_mod.importlib_metadata.PackageNotFoundError),
    )

    result = _mod.evaluate_requirement("pypdf>=6.7.5,<7.0")

    assert result.status == "missing"
    assert result.installed is None


def test_evaluate_requirement_reports_drift(monkeypatch):
    monkeypatch.setattr(_mod.importlib_metadata, "version", lambda name: "5.0.0")
    monkeypatch.setattr(_mod, "distribution_has_native_extensions", lambda name: False)

    result = _mod.evaluate_requirement("fastapi>=0.115.0,<1.0")

    assert result.status == "drift"
    assert result.installed == "5.0.0"


def test_evaluate_requirement_reports_invalid_installed_version(monkeypatch):
    monkeypatch.setattr(_mod.importlib_metadata, "version", lambda name: "not-a-version")
    monkeypatch.setattr(_mod, "distribution_has_native_extensions", lambda name: True)

    result = _mod.evaluate_requirement("fastapi>=0.115.0,<1.0")

    assert result.status == "invalid-installed-version"
    assert result.installed == "not-a-version"
    assert result.has_native_extensions is True


def test_distribution_has_native_extensions(monkeypatch):
    class FakeDist:
        files = ["pkg/native.so", "pkg/__init__.py"]

    monkeypatch.setattr(_mod.importlib_metadata, "distribution", lambda name: FakeDist())

    assert _mod.distribution_has_native_extensions("chromadb") is True


def test_check_constraints_reports_pyproject_alignment_and_status(tmp_path, monkeypatch):
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        """
[project]
dependencies = [
  "fastapi>=0.115.0,<1.0",
  "pypdf>=6.7.5,<7.0",
]
""".strip(),
        encoding="utf-8",
    )
    constraints = tmp_path / "constraints.txt"
    constraints.write_text("fastapi>=0.115.0,<1.0\n", encoding="utf-8")

    monkeypatch.setattr(_mod.importlib_metadata, "version", lambda name: "0.135.1")
    monkeypatch.setattr(_mod, "distribution_has_native_extensions", lambda name: False)

    report = _mod.check_constraints(pyproject_path=pyproject, constraints_path=constraints)

    assert report["missing_from_constraints"] == ["pypdf>=6.7.5,<7.0"]
    assert report["extra_in_constraints"] == []
    assert report["requirements"][0]["status"] == "ok"


def test_check_constraints_normalizes_equivalent_requirement_strings(tmp_path, monkeypatch):
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        """
[project]
dependencies = [
  "fastapi <1.0, >=0.115.0",
]
""".strip(),
        encoding="utf-8",
    )
    constraints = tmp_path / "constraints.txt"
    constraints.write_text("fastapi>=0.115.0,<1.0\n", encoding="utf-8")

    monkeypatch.setattr(_mod.importlib_metadata, "version", lambda name: "0.135.1")
    monkeypatch.setattr(_mod, "distribution_has_native_extensions", lambda name: False)

    report = _mod.check_constraints(pyproject_path=pyproject, constraints_path=constraints)

    assert report["missing_from_constraints"] == []
    assert report["extra_in_constraints"] == []


def test_main_json_output_and_exit_code(tmp_path, monkeypatch, capsys):
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        """
[project]
dependencies = [
  "fastapi>=0.115.0,<1.0",
]
""".strip(),
        encoding="utf-8",
    )
    constraints = tmp_path / "constraints.txt"
    constraints.write_text("fastapi>=0.115.0,<1.0\n", encoding="utf-8")

    monkeypatch.setattr(_mod.importlib_metadata, "version", lambda name: "0.135.1")
    monkeypatch.setattr(_mod, "distribution_has_native_extensions", lambda name: False)

    rc = _mod.main(
        ["--pyproject", str(pyproject), "--constraints", str(constraints), "--json"]
    )

    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["requirements"][0]["status"] == "ok"


def test_main_returns_failure_for_invalid_requirement_in_constraints(tmp_path, capsys):
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        """
[project]
dependencies = [
  "fastapi>=0.115.0,<1.0",
]
""".strip(),
        encoding="utf-8",
    )
    constraints = tmp_path / "constraints.txt"
    constraints.write_text("not a valid requirement >>>\n", encoding="utf-8")

    rc = _mod.main(
        ["--pyproject", str(pyproject), "--constraints", str(constraints), "--json"]
    )

    assert rc == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["requirements"][0]["status"] == "invalid-requirement"
