# -*- coding: utf-8 -*-
# Calibre-Web Automated – fork of Calibre-Web
# Copyright (C) 2026 Calibre-Web Automated contributors
# SPDX-License-Identifier: GPL-3.0-or-later

import importlib.util
import os
import sys
import types
from unittest.mock import MagicMock

import pytest


MODULE_NAME = "ldap_filter_test_package.services.simpleldap"
MODULE_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "../../cps/services/simpleldap.py")
)


@pytest.fixture
def simpleldap_module(monkeypatch):
    """Load simpleldap with only its LDAP and project dependencies mocked."""
    package = types.ModuleType("ldap_filter_test_package")
    package.__path__ = []
    services = types.ModuleType("ldap_filter_test_package.services")
    services.__path__ = []

    logger = types.ModuleType("ldap_filter_test_package.logger")
    logger.create = MagicMock(return_value=MagicMock())
    constants = types.ModuleType("ldap_filter_test_package.constants")

    flask = types.ModuleType("flask")
    flask.current_app = MagicMock()

    class LDAP:
        pass

    class LDAPException(Exception):
        message = ""

    flask_simpleldap = types.ModuleType("flask_simpleldap")
    flask_simpleldap.LDAP = LDAP
    flask_simpleldap.LDAPException = LDAPException
    flask_simpleldap.ldap = types.SimpleNamespace(LDAPError=Exception)

    module_patches = {
        MODULE_NAME.split(".services")[0]: package,
        MODULE_NAME.rsplit(".simpleldap", 1)[0]: services,
        f"{MODULE_NAME.split('.services')[0]}.logger": logger,
        f"{MODULE_NAME.split('.services')[0]}.constants": constants,
        "flask": flask,
        "flask_simpleldap": flask_simpleldap,
    }
    for name, module in module_patches.items():
        monkeypatch.setitem(sys.modules, name, module)

    spec = importlib.util.spec_from_file_location(MODULE_NAME, MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, MODULE_NAME, module)
    spec.loader.exec_module(module)
    return module


def test_escape_ldap_filter_escapes_all_rfc4515_filter_metacharacters(simpleldap_module):
    assert simpleldap_module._escape_ldap_filter("\\*()\x00") == r"\5c\2a\28\29\00"


def test_bind_user_escapes_username_for_lookup_and_bind(simpleldap_module):
    ldap = MagicMock()
    ldap.get_object_details.return_value = {"uid": "safe-user"}
    ldap.bind_user.return_value = object()
    simpleldap_module._ldap = ldap

    username = "*)(uid=*))(|(uid=*"
    result = simpleldap_module.bind_user(username, "password")

    escaped_username = r"\2a\29\28uid=\2a\29\29\28|\28uid=\2a"
    assert result == (True, None)
    ldap.get_object_details.assert_called_once_with(escaped_username)
    ldap.bind_user.assert_called_once_with(escaped_username, "password")


def test_bind_user_does_not_bind_when_escaped_username_is_not_found(simpleldap_module):
    ldap = MagicMock()
    ldap.get_object_details.return_value = None
    simpleldap_module._ldap = ldap

    assert simpleldap_module.bind_user("unknown*", "password") == (None, None)
    ldap.get_object_details.assert_called_once_with(r"unknown\2a")
    ldap.bind_user.assert_not_called()
