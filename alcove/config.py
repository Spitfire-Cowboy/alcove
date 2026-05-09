from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True, slots=True)
class Features:
    """Runtime feature flags.

    Flags default to conservative values so unset local installs behave the
    same as a fresh Alcove instance. Environment variables always override
    config-file values.
    """

    recent_activity: bool = False
    uploads: bool = True
    auth: bool = False
    turnstile: bool = False
    keyword_mode: bool = False
    date_filter: bool = False
    score_filter: bool = False
    project_filter: bool = False
    attribution: bool = False


@dataclass(frozen=True, slots=True)
class Deployment:
    """Deployment identity metadata."""

    mode: str = "local"
    instance_name: str = "Alcove"


@dataclass(frozen=True, slots=True)
class RuntimeConfig:
    features: Features = field(default_factory=Features)
    deployment: Deployment = field(default_factory=Deployment)
    recent_activity_limit: int = 5
    excerpt_chars: int | None = None
    private_mode: bool = True


def load_config() -> RuntimeConfig:
    values = _load_config_values()
    return RuntimeConfig(
        features=Features(
            recent_activity=_resolve_bool(
                env_name="ALCOVE_FEATURE_RECENT_ACTIVITY",
                config_value=values.get("features.recent_activity"),
                default=False,
            ),
            uploads=_resolve_bool(
                env_name="ALCOVE_ENABLE_UPLOADS",
                config_value=values.get("features.uploads"),
                default=True,
            ),
            auth=_resolve_bool(
                env_name="ALCOVE_ENABLE_AUTH",
                config_value=values.get("features.auth"),
                default=False,
            ),
            turnstile=_resolve_bool(
                env_name="ALCOVE_ENABLE_TURNSTILE",
                config_value=values.get("features.turnstile"),
                default=False,
            ),
            keyword_mode=_resolve_bool(
                env_name="ALCOVE_ENABLE_KEYWORD_MODE",
                config_value=values.get("features.keyword_mode"),
                default=False,
            ),
            date_filter=_resolve_bool(
                env_name="ALCOVE_ENABLE_DATE_FILTER",
                config_value=values.get("features.date_filter"),
                default=False,
            ),
            score_filter=_resolve_bool(
                env_name="ALCOVE_ENABLE_SCORE_FILTER",
                config_value=values.get("features.score_filter"),
                default=False,
            ),
            project_filter=_resolve_bool(
                env_name="ALCOVE_ENABLE_PROJECT_FILTER",
                config_value=values.get("features.project_filter"),
                default=False,
            ),
            attribution=_resolve_bool(
                env_name="ALCOVE_ENABLE_ATTRIBUTION",
                config_value=values.get("features.attribution"),
                default=False,
            ),
        ),
        deployment=Deployment(
            mode=_resolve_str(
                env_name="ALCOVE_DEPLOYMENT_MODE",
                config_value=values.get("deployment.mode"),
                default="local",
                choices={"local", "demo", "hosted"},
            ),
            instance_name=_resolve_str(
                env_name="ALCOVE_INSTANCE_NAME",
                config_value=values.get("deployment.instance_name"),
                default="Alcove",
            ),
        ),
        recent_activity_limit=_resolve_int(
            env_name="ALCOVE_RECENT_ACTIVITY_LIMIT",
            config_value=values.get("features.recent_activity_limit"),
            default=5,
            minimum=1,
        ),
        excerpt_chars=_resolve_optional_int(
            env_name="ALCOVE_EXCERPT_CHARS",
            config_value=values.get("excerpt_chars"),
            minimum=1,
        ),
        private_mode=_resolve_bool(
            env_name="ALCOVE_PRIVATE",
            config_value=values.get("private_mode"),
            default=True,
        ),
    )


def set_private_mode(enabled: bool) -> None:
    """Persist ``private_mode`` to an Alcove TOML config file."""
    path = Path(os.getenv("ALCOVE_CONFIG_PATH", "alcove.toml"))
    if path.suffix.lower() == ".json":
        raise ValueError("set_private_mode does not support JSON config files; use alcove.toml")

    value_str = "true" if enabled else "false"
    if path.is_file():
        lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
        new_lines: list[str] = []
        replaced = False
        for line in lines:
            stripped = line.split("#", 1)[0].strip()
            if stripped.startswith("private_mode") and "=" in stripped:
                new_lines.append(f"private_mode = {value_str}\n")
                replaced = True
            else:
                new_lines.append(line)
        if not replaced:
            if new_lines and not new_lines[-1].endswith("\n"):
                new_lines.append("\n")
            new_lines.append(f"private_mode = {value_str}\n")
        path.write_text("".join(new_lines), encoding="utf-8")
    else:
        path.write_text(f"private_mode = {value_str}\n", encoding="utf-8")


def _load_config_values() -> dict[str, object]:
    path = Path(os.getenv("ALCOVE_CONFIG_PATH", "alcove.toml"))
    if not path.is_file():
        return {}
    if path.suffix.lower() == ".json":
        return _load_json_values(path)
    return _load_toml_values(path)


def _load_json_values(path: Path) -> dict[str, object]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}

    out: dict[str, object] = {}
    features = data.get("features")
    if isinstance(features, dict):
        for key, value in features.items():
            out[f"features.{key}"] = value

    deployment = data.get("deployment")
    if isinstance(deployment, dict):
        for key, value in deployment.items():
            out[f"deployment.{key}"] = value

    if "excerpt_chars" in data:
        out["excerpt_chars"] = data["excerpt_chars"]
    if "private_mode" in data:
        out["private_mode"] = data["private_mode"]

    return out


def _load_toml_values(path: Path) -> dict[str, object]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return {}

    values: dict[str, object] = {}
    current_section: tuple[str, ...] = ()
    for raw_line in lines:
        line = raw_line.split("#", 1)[0].strip()
        if not line:
            continue
        if line.startswith("[") and line.endswith("]"):
            current_section = tuple(part.strip() for part in line[1:-1].split(".") if part.strip())
            continue
        if "=" not in line:
            continue

        key, raw_value = (part.strip() for part in line.split("=", 1))
        full_key = ".".join((*current_section, key)) if current_section else key
        values[full_key] = _parse_scalar(raw_value)
    return values


def _parse_scalar(raw_value: str) -> object:
    if raw_value.startswith(("'", '"')) and raw_value.endswith(("'", '"')):
        return raw_value[1:-1]

    lowered = raw_value.lower()
    if lowered in {"true", "false"}:
        return lowered == "true"

    try:
        return int(raw_value)
    except ValueError:
        return raw_value


def _resolve_bool(*, env_name: str, config_value: object, default: bool) -> bool:
    env_value = os.getenv(env_name)
    if env_value is not None:
        parsed = _coerce_bool(env_value)
        return default if parsed is None else parsed

    parsed = _coerce_bool(config_value)
    return default if parsed is None else parsed


def _resolve_str(
    *,
    env_name: str,
    config_value: object,
    default: str,
    choices: set[str] | None = None,
) -> str:
    env_value = os.getenv(env_name)
    if env_value is not None:
        value = env_value.strip()
        if choices:
            value = value.lower()
            if value not in choices:
                return default
        return value

    if isinstance(config_value, str):
        value = config_value.strip()
        if choices:
            value = value.lower()
            if value not in choices:
                return default
        return value

    return default


def _resolve_int(*, env_name: str, config_value: object, default: int, minimum: int) -> int:
    env_value = os.getenv(env_name)
    if env_value is not None:
        parsed = _coerce_int(env_value)
        return default if parsed is None else max(minimum, parsed)

    parsed = _coerce_int(config_value)
    return default if parsed is None else max(minimum, parsed)


def _resolve_optional_int(*, env_name: str, config_value: object, minimum: int) -> int | None:
    env_value = os.getenv(env_name)
    if env_value is not None:
        parsed = _coerce_int(env_value)
        return None if parsed is None else max(minimum, parsed)

    parsed = _coerce_int(config_value)
    return None if parsed is None else max(minimum, parsed)


def _coerce_bool(value: object) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return bool(value)
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"1", "true", "yes", "on"}:
            return True
        if lowered in {"0", "false", "no", "off"}:
            return False
    return None


def _coerce_int(value: object) -> int | None:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value.strip())
        except ValueError:
            return None
    return None
