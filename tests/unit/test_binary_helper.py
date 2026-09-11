# -*- coding: utf-8 -*-
# Calibre-Web Automated – fork of Calibre-Web
# SPDX-License-Identifier: GPL-3.0-or-later

"""Regression tests for configured optional executable resolution."""

import pytest

from binary_helper import (
    SUPPORTED_KEPUBIFY_BINARIES,
    SUPPORTED_UNRAR_BINARIES,
    resolve_binary_path,
)


pytestmark = pytest.mark.unit


def _executable(path):
    path.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    path.chmod(0o755)
    return path


def test_allowed_configured_unrar_file_is_preserved(tmp_path):
    configured = _executable(tmp_path / SUPPORTED_UNRAR_BINARIES[0])

    assert resolve_binary_path(str(configured), SUPPORTED_UNRAR_BINARIES) == str(configured)


def test_allowed_binary_can_be_selected_from_configured_directory(tmp_path):
    configured = _executable(tmp_path / SUPPORTED_KEPUBIFY_BINARIES[-1])

    assert resolve_binary_path(str(tmp_path), SUPPORTED_KEPUBIFY_BINARIES) == str(configured)


def test_arbitrary_configured_executable_name_is_rejected(tmp_path):
    configured = _executable(tmp_path / "run-anything")

    assert resolve_binary_path(str(configured), SUPPORTED_UNRAR_BINARIES) == ""


def test_empty_or_missing_configuration_disables_helper(tmp_path):
    assert resolve_binary_path("", SUPPORTED_UNRAR_BINARIES) == ""
    assert resolve_binary_path(None, SUPPORTED_KEPUBIFY_BINARIES) == ""
    assert resolve_binary_path(str(tmp_path / "missing"), SUPPORTED_KEPUBIFY_BINARIES) == ""


def test_non_executable_allowed_name_is_rejected(tmp_path):
    configured = tmp_path / SUPPORTED_UNRAR_BINARIES[0]
    configured.write_text("#!/bin/sh\n", encoding="utf-8")
    configured.chmod(0o644)

    assert resolve_binary_path(str(configured), SUPPORTED_UNRAR_BINARIES) == ""
