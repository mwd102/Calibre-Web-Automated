"""Kobo diagnostics must never persist the device credential."""
import logging
from types import SimpleNamespace

import pytest
from flask import Flask

from cps import logger
from cps import kobo


@pytest.mark.parametrize('formatter', [logger.ACCESS_FORMATTER_GEVENT,
                                     logger.ACCESS_FORMATTER_TORNADO, logger.FORMATTER])
@pytest.mark.parametrize('path', ['/kobo/device-secret/v1/library/sync',
                                  '/prefix/kobo/device-secret',
                                  '/kobo/device-secret?x=1'])
def test_kobo_token_redacted_after_message_interpolation(formatter, path):
    record = logging.LogRecord('test', logging.INFO, __file__, 1,
                               'GET %s HTTP/1.1 401', (path,), None)
    output = formatter.format(record)
    assert 'device-secret' not in output
    assert '/kobo/[REDACTED]' in output
    assert '401' in output


@pytest.mark.parametrize('enabled', [True, False])
@pytest.mark.parametrize('authenticated', [True, False])
def test_kobo_request_logging_has_account_and_status_without_credentials(monkeypatch, enabled, authenticated):
    monkeypatch.setattr(kobo, 'config', SimpleNamespace(config_access_log=enabled))
    monkeypatch.setattr(kobo, 'current_user', SimpleNamespace(id=7, is_authenticated=authenticated))
    messages = []
    monkeypatch.setattr(kobo.log, 'info', lambda msg, *args: messages.append(msg % args))
    app = Flask(__name__)
    app.add_url_rule('/kobo/<token>/v1/library/sync', endpoint='kobo.HandleSyncRequest', view_func=lambda token: '')
    with app.test_request_context('/kobo/device-secret/v1/library/sync?secret=hidden'):
        response = app.response_class(status=401)
        assert kobo.log_kobo_request(response) is response
    assert len(messages) == int(enabled)
    if enabled:
        assert ('user_id=7' if authenticated else 'user_id=anonymous') in messages[0]
        assert 'endpoint=kobo.HandleSyncRequest status=401' in messages[0]
        assert 'device-secret' not in messages[0]
        assert 'hidden' not in messages[0]
