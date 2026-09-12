"""Regression tests for credentials omitted from debug settings."""

from cps.config_sql import ConfigSQL


def test_to_dict_excludes_api_keys_tokens_secrets_and_passwords():
    config = ConfigSQL()
    config.config_goodreads_api_key = "goodreads-api-key"
    config.config_hardcover_token = "hardcover-token"
    config.mail_gmail_token = {"refresh_token": "gmail-refresh-token"}
    config.oauth_client_secret = "oauth-client-secret"
    config.mail_password = "smtp-password"
    config.config_ldap_serv_password = "ldap-password"

    settings = config.to_dict()

    assert "config_goodreads_api_key" not in settings
    assert "config_hardcover_token" not in settings
    assert "mail_gmail_token" not in settings
    assert "oauth_client_secret" not in settings
    assert "mail_password" not in settings
    assert "config_ldap_serv_password" not in settings


def test_to_dict_keeps_non_sensitive_configuration():
    config = ConfigSQL()
    config.config_calibre_web_title = "Library"
    config.config_password_policy = True
    config.config_password_min_length = 12

    settings = config.to_dict()

    assert settings["config_calibre_web_title"] == "Library"
    assert settings["config_password_policy"] is True
    assert settings["config_password_min_length"] == 12
