from __future__ import annotations

import json

import pytest

from alcove.config import Deployment, Features, RuntimeConfig, load_config, set_private_mode


def test_default_features_are_conservative():
    features = Features()
    assert features.uploads is True
    assert features.auth is False
    assert features.turnstile is False
    assert features.keyword_mode is False
    assert features.date_filter is False
    assert features.score_filter is False
    assert features.project_filter is False
    assert features.attribution is False


def test_default_deployment_identity():
    deployment = Deployment()
    assert deployment.mode == "local"
    assert deployment.instance_name == "Alcove"


def test_default_private_mode_is_true(monkeypatch):
    monkeypatch.delenv("ALCOVE_PRIVATE", raising=False)
    monkeypatch.delenv("ALCOVE_CONFIG_PATH", raising=False)
    assert RuntimeConfig().private_mode is True
    assert load_config().private_mode is True


def test_env_bool_overrides(monkeypatch):
    monkeypatch.delenv("ALCOVE_CONFIG_PATH", raising=False)
    monkeypatch.setenv("ALCOVE_ENABLE_UPLOADS", "0")
    monkeypatch.setenv("ALCOVE_ENABLE_AUTH", "1")
    monkeypatch.setenv("ALCOVE_ENABLE_TURNSTILE", "true")
    monkeypatch.setenv("ALCOVE_ENABLE_KEYWORD_MODE", "yes")
    monkeypatch.setenv("ALCOVE_ENABLE_DATE_FILTER", "on")
    monkeypatch.setenv("ALCOVE_ENABLE_SCORE_FILTER", "1")
    monkeypatch.setenv("ALCOVE_ENABLE_PROJECT_FILTER", "true")
    monkeypatch.setenv("ALCOVE_ENABLE_ATTRIBUTION", "yes")
    monkeypatch.setenv("ALCOVE_PRIVATE", "false")

    cfg = load_config()
    assert cfg.features.uploads is False
    assert cfg.features.auth is True
    assert cfg.features.turnstile is True
    assert cfg.features.keyword_mode is True
    assert cfg.features.date_filter is True
    assert cfg.features.score_filter is True
    assert cfg.features.project_filter is True
    assert cfg.features.attribution is True
    assert cfg.private_mode is False


def test_env_deployment_overrides(monkeypatch):
    monkeypatch.delenv("ALCOVE_CONFIG_PATH", raising=False)
    monkeypatch.setenv("ALCOVE_DEPLOYMENT_MODE", "demo")
    monkeypatch.setenv("ALCOVE_INSTANCE_NAME", "Community Archive")

    cfg = load_config()
    assert cfg.deployment.mode == "demo"
    assert cfg.deployment.instance_name == "Community Archive"


def test_invalid_deployment_mode_falls_back(monkeypatch):
    monkeypatch.delenv("ALCOVE_CONFIG_PATH", raising=False)
    monkeypatch.setenv("ALCOVE_DEPLOYMENT_MODE", "cloud")

    assert load_config().deployment.mode == "local"


def test_numeric_env_overrides(monkeypatch):
    monkeypatch.delenv("ALCOVE_CONFIG_PATH", raising=False)
    monkeypatch.setenv("ALCOVE_RECENT_ACTIVITY_LIMIT", "12")
    monkeypatch.setenv("ALCOVE_EXCERPT_CHARS", "350")

    cfg = load_config()
    assert cfg.recent_activity_limit == 12
    assert cfg.excerpt_chars == 350


def test_invalid_numeric_env_uses_defaults(monkeypatch):
    monkeypatch.delenv("ALCOVE_CONFIG_PATH", raising=False)
    monkeypatch.setenv("ALCOVE_RECENT_ACTIVITY_LIMIT", "many")
    monkeypatch.setenv("ALCOVE_EXCERPT_CHARS", "wide")

    cfg = load_config()
    assert cfg.recent_activity_limit == 5
    assert cfg.excerpt_chars is None


def test_toml_feature_flags(tmp_path, monkeypatch):
    toml = tmp_path / "alcove.toml"
    toml.write_text(
        "excerpt_chars = 250\n"
        "private_mode = false\n"
        "[features]\n"
        "uploads = false\n"
        "auth = true\n"
        "keyword_mode = true\n"
        "recent_activity_limit = 9\n"
        "[deployment]\n"
        'mode = "hosted"\n'
        'instance_name = "My Archive"\n',
        encoding="utf-8",
    )
    monkeypatch.setenv("ALCOVE_CONFIG_PATH", str(toml))
    for env_name in (
        "ALCOVE_ENABLE_UPLOADS",
        "ALCOVE_ENABLE_AUTH",
        "ALCOVE_ENABLE_KEYWORD_MODE",
        "ALCOVE_DEPLOYMENT_MODE",
        "ALCOVE_INSTANCE_NAME",
        "ALCOVE_RECENT_ACTIVITY_LIMIT",
        "ALCOVE_EXCERPT_CHARS",
        "ALCOVE_PRIVATE",
    ):
        monkeypatch.delenv(env_name, raising=False)

    cfg = load_config()
    assert cfg.features.uploads is False
    assert cfg.features.auth is True
    assert cfg.features.keyword_mode is True
    assert cfg.recent_activity_limit == 9
    assert cfg.deployment.mode == "hosted"
    assert cfg.deployment.instance_name == "My Archive"
    assert cfg.excerpt_chars == 250
    assert cfg.private_mode is False


def test_json_feature_flags(tmp_path, monkeypatch):
    config_file = tmp_path / "alcove.json"
    config_file.write_text(
        json.dumps(
            {
                "features": {"uploads": False, "turnstile": True},
                "deployment": {"mode": "hosted", "instance_name": "Demo Archive"},
                "excerpt_chars": 120,
                "private_mode": False,
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("ALCOVE_CONFIG_PATH", str(config_file))

    cfg = load_config()
    assert cfg.features.uploads is False
    assert cfg.features.turnstile is True
    assert cfg.deployment.mode == "hosted"
    assert cfg.deployment.instance_name == "Demo Archive"
    assert cfg.excerpt_chars == 120
    assert cfg.private_mode is False


def test_env_wins_over_config_file(tmp_path, monkeypatch):
    toml = tmp_path / "alcove.toml"
    toml.write_text("[features]\nuploads = false\n", encoding="utf-8")
    monkeypatch.setenv("ALCOVE_CONFIG_PATH", str(toml))
    monkeypatch.setenv("ALCOVE_ENABLE_UPLOADS", "1")

    assert load_config().features.uploads is True


def test_config_objects_are_frozen(monkeypatch):
    monkeypatch.delenv("ALCOVE_CONFIG_PATH", raising=False)
    cfg = load_config()
    with pytest.raises((AttributeError, TypeError)):
        cfg.features.uploads = False  # type: ignore[misc]
    with pytest.raises((AttributeError, TypeError)):
        cfg.deployment.mode = "hosted"  # type: ignore[misc]


def test_set_private_mode_creates_toml_when_file_missing(tmp_path, monkeypatch):
    toml = tmp_path / "alcove.toml"
    monkeypatch.setenv("ALCOVE_CONFIG_PATH", str(toml))

    set_private_mode(False)

    assert toml.read_text(encoding="utf-8") == "private_mode = false\n"


def test_set_private_mode_updates_existing_key(tmp_path, monkeypatch):
    toml = tmp_path / "alcove.toml"
    toml.write_text("private_mode = true\n", encoding="utf-8")
    monkeypatch.setenv("ALCOVE_CONFIG_PATH", str(toml))

    set_private_mode(False)

    assert toml.read_text(encoding="utf-8") == "private_mode = false\n"


def test_set_private_mode_preserves_other_keys(tmp_path, monkeypatch):
    toml = tmp_path / "alcove.toml"
    toml.write_text("[features]\nuploads = true\n", encoding="utf-8")
    monkeypatch.setenv("ALCOVE_CONFIG_PATH", str(toml))

    set_private_mode(True)

    content = toml.read_text(encoding="utf-8")
    assert "uploads = true" in content
    assert "private_mode = true" in content


def test_set_private_mode_rejects_json_config(tmp_path, monkeypatch):
    config_file = tmp_path / "alcove.json"
    config_file.write_text("{}", encoding="utf-8")
    monkeypatch.setenv("ALCOVE_CONFIG_PATH", str(config_file))

    with pytest.raises(ValueError, match="JSON"):
        set_private_mode(False)
