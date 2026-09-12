# Calibre-Web Automated – fork of Calibre-Web
# Copyright (C) 2024-2026 Calibre-Web Automated contributors
# SPDX-License-Identifier: GPL-3.0-or-later
# See CONTRIBUTORS for the full list of authors.

"""Helpers for loading secrets from environment variables or secret files."""

import logging
import os

log = logging.getLogger(__name__)

# These are the sensitive environment variables currently consumed by CWA.
# The resolver itself remains generic so a future sensitive setting can adopt
# the same convention without duplicating file-loading logic.
SUPPORTED_SECRET_VARIABLES = frozenset({"SECRET_KEY", "HARDCOVER_TOKEN"})
DEFAULT_SECRET_DIR = "/run/secrets"


def _read_secret_file(path: str, variable_name: str, warn_if_missing: bool = True) -> str | None:
    """Read a UTF-8 secret file, removing Docker's conventional final newline.

    Secret values are never included in log messages.  A missing or unreadable
    file is treated as an unavailable source so callers can use their normal
    application fallback.
    """
    try:
        with open(path, "r", encoding="utf-8") as secret_file:
            return secret_file.read().rstrip("\r\n")
    except FileNotFoundError:
        if warn_if_missing:
            log.warning("Could not read secret for %s from the configured file", variable_name)
        return None
    except (OSError, UnicodeError, ValueError):
        log.warning("Could not read secret for %s from the configured file", variable_name)
        return None


def get_secret(variable_name: str, default_value: str | None = None) -> str | None:
    """Return a secret using CWA's environment/file precedence.

    The non-empty value in ``variable_name`` takes precedence.  If it is not
    set, ``variable_name_FILE`` is treated as a path to a UTF-8 file.  Finally,
    Docker's conventional ``/run/secrets/<variable_name>`` path is checked.
    ``default_value`` is returned when no source is available.

    Direct environment variables remain supported for existing deployments.
    Empty values are treated as unset, which allows a compose placeholder such
    as ``HARDCOVER_TOKEN=`` to coexist with ``HARDCOVER_TOKEN_FILE``.
    """
    direct_value = os.getenv(variable_name)
    if direct_value:
        return direct_value

    file_path = os.getenv(f"{variable_name}_FILE")
    if file_path:
        file_value = _read_secret_file(file_path, variable_name)
        if file_value is not None:
            return file_value

    default_path = os.path.join(DEFAULT_SECRET_DIR, variable_name)
    file_value = _read_secret_file(default_path, variable_name, warn_if_missing=False)
    if file_value is not None:
        return file_value

    return default_value
