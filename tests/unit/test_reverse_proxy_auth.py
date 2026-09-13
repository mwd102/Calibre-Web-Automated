"""Preserve live proxy authentication, including spoofed forwarded addresses."""
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from cps import usermanagement


@pytest.mark.parametrize('peer,forwarded,secret,enabled,expected', [
    ('fd42:42::12', '198.51.100.5', 'correct', True, True),
    ('127.0.0.1', None, 'correct', True, True),
    ('198.51.100.5', '127.0.0.1', 'correct', True, False),
    ('fd42:42::12', None, None, True, False),
    ('fd42:42::12', None, 'wrong', True, False),
    ('fd42:42::12', None, None, False, True),
    ('invalid', None, 'correct', True, False),
])
def test_proxy_boundary(monkeypatch, peer, forwarded, secret, enabled, expected):
    config = SimpleNamespace(config_reverse_proxy_trusted_ips='127.0.0.1,::1,fd42:42::/56',
        config_reverse_proxy_use_shared_secret=enabled,
        config_reverse_proxy_login_secret_header_name='X-Proxy-Secret',
        config_reverse_proxy_login_header_secret_e='correct')
    monkeypatch.setattr(usermanagement, 'config', config)
    request = SimpleNamespace(remote_addr=forwarded or peer,
        environ={'werkzeug.proxy_fix.orig': {'REMOTE_ADDR': peer}} if forwarded else {},
        headers={'X-Proxy-Secret':secret})
    assert usermanagement._is_reverse_proxy_authenticated(request) is expected


def test_rejected_header_never_looks_up_user(monkeypatch):
    monkeypatch.setattr(usermanagement, 'config', SimpleNamespace(config_reverse_proxy_login_header_name='X-User'))
    monkeypatch.setattr(usermanagement, '_is_reverse_proxy_authenticated', lambda req: False)
    session = Mock()
    monkeypatch.setattr(usermanagement.ub, 'session', session)
    assert usermanagement.load_user_from_reverse_proxy_header(SimpleNamespace(headers={'X-User':'admin'})) is None
    session.query.assert_not_called()
