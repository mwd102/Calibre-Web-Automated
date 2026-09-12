"""Focused tests for Docker-compatible secret configuration."""

import logging

from cps import secret_helper


def test_direct_environment_value_takes_precedence(monkeypatch, tmp_path):
    secret_file = tmp_path / "hardcover-token"
    secret_file.write_text("file-token\n", encoding="utf-8")
    monkeypatch.setenv("HARDCOVER_TOKEN", "environment-token")
    monkeypatch.setenv("HARDCOVER_TOKEN_FILE", str(secret_file))

    assert secret_helper.get_secret("HARDCOVER_TOKEN") == "environment-token"


def test_file_environment_value_is_loaded_and_trailing_newline_removed(monkeypatch, tmp_path):
    secret_file = tmp_path / "secret-key"
    secret_file.write_text("file-secret\r\n", encoding="utf-8")
    monkeypatch.delenv("SECRET_KEY", raising=False)
    monkeypatch.setenv("SECRET_KEY_FILE", str(secret_file))

    assert secret_helper.get_secret("SECRET_KEY") == "file-secret"


def test_empty_direct_environment_value_falls_back_to_file(monkeypatch, tmp_path):
    secret_file = tmp_path / "token"
    secret_file.write_text("file-token\n", encoding="utf-8")
    monkeypatch.setenv("HARDCOVER_TOKEN", "")
    monkeypatch.setenv("HARDCOVER_TOKEN_FILE", str(secret_file))

    assert secret_helper.get_secret("HARDCOVER_TOKEN") == "file-token"


def test_default_docker_secret_path_is_supported(monkeypatch, tmp_path):
    secret_dir = tmp_path / "run-secrets"
    secret_dir.mkdir()
    (secret_dir / "SECRET_KEY").write_text("docker-secret\n", encoding="utf-8")
    monkeypatch.delenv("SECRET_KEY", raising=False)
    monkeypatch.delenv("SECRET_KEY_FILE", raising=False)
    monkeypatch.setattr(secret_helper, "DEFAULT_SECRET_DIR", str(secret_dir))

    assert secret_helper.get_secret("SECRET_KEY") == "docker-secret"


def test_missing_or_unreadable_sources_return_default(monkeypatch, tmp_path):
    missing_file = tmp_path / "missing"
    monkeypatch.delenv("HARDCOVER_TOKEN", raising=False)
    monkeypatch.setenv("HARDCOVER_TOKEN_FILE", str(missing_file))
    monkeypatch.setattr(secret_helper, "DEFAULT_SECRET_DIR", str(tmp_path / "no-secrets"))

    assert secret_helper.get_secret("HARDCOVER_TOKEN", "database-token") == "database-token"


def test_missing_default_docker_secret_is_quiet(monkeypatch, tmp_path, caplog):
    monkeypatch.delenv("SECRET_KEY", raising=False)
    monkeypatch.delenv("SECRET_KEY_FILE", raising=False)
    monkeypatch.setattr(secret_helper, "DEFAULT_SECRET_DIR", str(tmp_path / "no-secrets"))

    with caplog.at_level(logging.WARNING, logger="cps.secret_helper"):
        assert secret_helper.get_secret("SECRET_KEY", "database-secret") == "database-secret"

    assert caplog.records == []


def test_secret_values_are_not_logged(monkeypatch, tmp_path, caplog):
    missing_file = tmp_path / "missing"
    monkeypatch.delenv("HARDCOVER_TOKEN", raising=False)
    monkeypatch.setenv("HARDCOVER_TOKEN_FILE", str(missing_file))
    monkeypatch.setattr(secret_helper, "DEFAULT_SECRET_DIR", str(tmp_path / "no-secrets"))

    with caplog.at_level(logging.WARNING, logger="cps.secret_helper"):
        secret_helper.get_secret("HARDCOVER_TOKEN")

    assert "HARDCOVER_TOKEN" in caplog.text
    assert "missing" not in caplog.text
