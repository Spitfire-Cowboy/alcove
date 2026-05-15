from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from importlib import metadata as importlib_metadata
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib

from packaging.requirements import InvalidRequirement, Requirement
from packaging.utils import canonicalize_name
from packaging.version import Version


_NATIVE_SUFFIXES = {".so", ".pyd", ".dylib", ".dll"}


@dataclass(frozen=True)
class ConstraintStatus:
    requirement: str
    name: str
    installed: str | None
    status: str
    has_native_extensions: bool


def load_pyproject_requirements(pyproject_path: Path) -> list[str]:
    with pyproject_path.open("rb") as fp:
        data = tomllib.load(fp)
    return list(data["project"]["dependencies"])


def load_constraints(constraints_path: Path) -> list[str]:
    requirements: list[str] = []
    for line in constraints_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        requirements.append(stripped)
    return requirements


def normalize_requirement(requirement_line: str) -> str:
    try:
        requirement = Requirement(requirement_line)
    except InvalidRequirement:
        return f"INVALID::{requirement_line.strip()}"

    parts = [canonicalize_name(requirement.name)]
    if requirement.extras:
        extras = ",".join(sorted(requirement.extras))
        parts[0] = f"{parts[0]}[{extras}]"
    if requirement.specifier:
        specifiers = ",".join(sorted(str(item) for item in requirement.specifier))
        parts.append(specifiers)
    if requirement.marker is not None:
        parts.append(f"; {requirement.marker}")
    if requirement.url:
        parts.append(f" @ {requirement.url}")
    return "".join(parts)


def check_constraints(
    *,
    pyproject_path: Path,
    constraints_path: Path,
) -> dict[str, object]:
    pyproject_reqs = load_pyproject_requirements(pyproject_path)
    constraint_reqs = load_constraints(constraints_path)

    pyproject_map = {normalize_requirement(req): req for req in pyproject_reqs}
    constraints_map = {normalize_requirement(req): req for req in constraint_reqs}

    pyproject_set = set(pyproject_map)
    constraints_set = set(constraints_map)

    statuses = [evaluate_requirement(req) for req in constraint_reqs]
    return {
        "constraints_path": str(constraints_path),
        "pyproject_path": str(pyproject_path),
        "missing_from_constraints": sorted(pyproject_map[key] for key in pyproject_set - constraints_set),
        "extra_in_constraints": sorted(constraints_map[key] for key in constraints_set - pyproject_set),
        "requirements": [status.__dict__ for status in statuses],
    }


def evaluate_requirement(requirement_line: str) -> ConstraintStatus:
    try:
        requirement = Requirement(requirement_line)
    except InvalidRequirement:
        return ConstraintStatus(
            requirement=requirement_line,
            name=requirement_line,
            installed=None,
            status="invalid-requirement",
            has_native_extensions=False,
        )
    if requirement.marker is not None and not requirement.marker.evaluate():
        return ConstraintStatus(
            requirement=requirement_line,
            name=requirement.name,
            installed=None,
            status="skipped-by-marker",
            has_native_extensions=False,
        )

    try:
        installed_version = importlib_metadata.version(requirement.name)
    except importlib_metadata.PackageNotFoundError:
        return ConstraintStatus(
            requirement=requirement_line,
            name=requirement.name,
            installed=None,
            status="missing",
            has_native_extensions=False,
        )

    installed = Version(installed_version)
    status = "ok" if installed in requirement.specifier else "drift"
    return ConstraintStatus(
        requirement=requirement_line,
        name=requirement.name,
        installed=installed_version,
        status=status,
        has_native_extensions=distribution_has_native_extensions(requirement.name),
    )


def distribution_has_native_extensions(name: str) -> bool:
    try:
        dist = importlib_metadata.distribution(name)
    except importlib_metadata.PackageNotFoundError:
        return False
    files = getattr(dist, "files", None) or []
    return any(Path(str(file)).suffix.lower() in _NATIVE_SUFFIXES for file in files)


def print_report(report: dict[str, object]) -> None:
    print(f"Constraints: {report['constraints_path']}")
    print(f"Pyproject:   {report['pyproject_path']}")

    missing = report["missing_from_constraints"]
    extra = report["extra_in_constraints"]
    if missing:
        print("Missing from constraints:")
        for item in missing:
            print(f"  {item}")
    if extra:
        print("Extra in constraints:")
        for item in extra:
            print(f"  {item}")

    print("Dependency status:")
    for item in report["requirements"]:
        installed = item["installed"] or "(not installed)"
        native = " native" if item["has_native_extensions"] else ""
        print(f"  {item['name']:18s} {item['status']:17s} {installed}{native}")


def exit_code(report: dict[str, object]) -> int:
    if report["missing_from_constraints"] or report["extra_in_constraints"]:
        return 1
    bad = {"missing", "drift", "invalid-requirement"}
    if any(item["status"] in bad for item in report["requirements"]):
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Check public dependency constraints drift and installed-package integrity."
    )
    parser.add_argument(
        "--pyproject",
        default="pyproject.toml",
        help="Path to pyproject.toml (default: pyproject.toml)",
    )
    parser.add_argument(
        "--constraints",
        default="constraints/base-runtime.txt",
        help="Path to constraints file (default: constraints/base-runtime.txt)",
    )
    parser.add_argument("--json", action="store_true", help="Emit JSON report")
    args = parser.parse_args(argv)

    report = check_constraints(
        pyproject_path=Path(args.pyproject),
        constraints_path=Path(args.constraints),
    )
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print_report(report)
    return exit_code(report)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
