"""Kobo Store proxying must not require process-wide proxy variables."""

from cps import kobo


def test_store_proxy_is_disabled_by_default(monkeypatch):
    monkeypatch.delenv("CWA_KOBO_STORE_PROXY", raising=False)
    assert kobo._store_proxy_settings() is None


def test_store_proxy_is_scoped_to_http_and_https(monkeypatch):
    monkeypatch.setenv("CWA_KOBO_STORE_PROXY", "http://residential-proxy:3128")
    assert kobo._store_proxy_settings() == {
        "http": "http://residential-proxy:3128",
        "https": "http://residential-proxy:3128",
    }
