# Calibre-Web Automated – fork of Calibre-Web
# Copyright (C) 2018-2026 Calibre-Web contributors
# Copyright (C) 2024-2026 Calibre-Web Automated contributors
# SPDX-License-Identifier: GPL-3.0-or-later

"""Authorization tests for the Kobo auth-token management endpoints."""

import importlib.util
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest


class ForbiddenResponse(Exception):
    """Minimal stand-in for Flask's HTTPException in isolated unit tests."""

    def __init__(self, code):
        self.code = code
        super().__init__(code)


class _Blueprint:
    def __init__(self, *args, **kwargs):
        pass

    def route(self, *args, **kwargs):
        return lambda function: function


class _Query:
    def __init__(self, token):
        self.token = token
        self.filter_calls = 0
        self.delete_calls = 0

    def filter(self, *args, **kwargs):
        self.filter_calls += 1
        return self

    def first(self):
        return self.token

    def delete(self):
        self.delete_calls += 1
        return 1


class _Session:
    def __init__(self, token):
        self.query_calls = 0
        self.query_result = _Query(token)
        self.commit_calls = 0

    def query(self, *args, **kwargs):
        self.query_calls += 1
        return self.query_result

    def commit(self):
        self.commit_calls += 1
        return "committed"


class _Logger:
    def debug(self, *args, **kwargs):
        pass

    def error(self, *args, **kwargs):
        pass


class _Column:
    def __eq__(self, other):
        return (self, other)


class _RemoteAuthToken:
    user_id = _Column()
    token_type = _Column()


@pytest.fixture
def kobo_auth_module(monkeypatch):
    """Load cps.kobo_auth with only the dependencies needed by these routes."""
    def install(name, **attributes):
        module = ModuleType(name)
        for key, value in attributes.items():
            setattr(module, key, value)
        monkeypatch.setitem(sys.modules, name, module)
        return module

    cps = install("cps")
    cps.__path__ = [str(Path(__file__).resolve().parents[2] / "cps")]

    flask = install(
        "flask",
        Blueprint=_Blueprint,
        abort=lambda code: (_ for _ in ()).throw(ForbiddenResponse(code)),
        g=SimpleNamespace(),
        request=SimpleNamespace(host="library.example"),
    )
    install("flask_babel", gettext=lambda value: value)
    install("flask_limiter", RateLimitExceeded=type("RateLimitExceeded", (Exception,), {}))

    logger = install("cps.logger", create=lambda: _Logger())
    config = install("cps.config")
    calibre_db = install("cps.calibre_db")
    db = install("cps.db")
    helper = install("cps.helper")
    ub = install("cps.ub", RemoteAuthToken=_RemoteAuthToken)
    lm = install("cps.lm")
    limiter = install("cps.limiter")
    render_template = install(
        "cps.render_template",
        render_title_template=lambda *args, **kwargs: "rendered",
    )
    usermanagement = install("cps.usermanagement", user_login_required=lambda function: function)
    cw_login = install(
        "cps.cw_login",
        current_user=SimpleNamespace(id=1, role_admin=lambda: False),
        login_user=lambda user: user,
    )

    for module in (logger, config, calibre_db, db, helper, ub, lm, limiter,
                   render_template, usermanagement, cw_login):
        setattr(cps, module.__name__.split(".")[-1], module)

    module_name = "cps.kobo_auth"
    module_path = Path(__file__).resolve().parents[2] / "cps" / "kobo_auth.py"
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    module = importlib.util.module_from_spec(spec)
    module.__package__ = "cps"
    monkeypatch.setitem(sys.modules, module_name, module)
    spec.loader.exec_module(module)

    # Keep the imported module's request object explicit for the endpoint tests.
    module.request = flask.request
    module.render_title_template = render_template.render_title_template
    return module


def _configure_request(module, *, current_user_id, is_admin):
    token = SimpleNamespace(auth_token="existing-token")
    session = _Session(token)
    module.ub.session = session
    module.ub.session_commit = session.commit
    module.current_user = SimpleNamespace(
        id=current_user_id,
        role_admin=lambda: is_admin,
    )
    return session


@pytest.mark.unit
@pytest.mark.parametrize(
    "endpoint",
    ["generate_auth_token", "delete_auth_token"],
)
def test_kobo_token_owner_is_allowed(kobo_auth_module, endpoint):
    session = _configure_request(kobo_auth_module, current_user_id=42, is_admin=False)

    result = getattr(kobo_auth_module, endpoint)(42)

    assert result in ("rendered", "committed")
    assert session.query_calls == 1


@pytest.mark.unit
@pytest.mark.parametrize(
    "endpoint",
    ["generate_auth_token", "delete_auth_token"],
)
def test_kobo_token_admin_is_allowed(kobo_auth_module, endpoint):
    session = _configure_request(kobo_auth_module, current_user_id=7, is_admin=True)

    result = getattr(kobo_auth_module, endpoint)(42)

    assert result in ("rendered", "committed")
    assert session.query_calls == 1


@pytest.mark.unit
@pytest.mark.parametrize(
    "endpoint",
    ["generate_auth_token", "delete_auth_token"],
)
def test_kobo_token_cross_user_is_forbidden(kobo_auth_module, endpoint):
    session = _configure_request(kobo_auth_module, current_user_id=7, is_admin=False)

    with pytest.raises(ForbiddenResponse) as error:
        getattr(kobo_auth_module, endpoint)(42)

    assert error.value.code == 403
    assert session.query_calls == 0
