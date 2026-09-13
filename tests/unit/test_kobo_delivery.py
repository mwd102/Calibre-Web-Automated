"""One-click Kobo delivery uses existing sync memberships and user boundaries."""
from datetime import datetime, timedelta
from inspect import unwrap
from types import SimpleNamespace

import pytest
from flask import Flask
from flask_babel import Babel
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from werkzeug.exceptions import HTTPException

from cps import kobo_delivery as delivery, ub


@pytest.fixture
def database(monkeypatch):
    engine = create_engine('sqlite://')
    ub.Base.metadata.create_all(engine, tables=[model.__table__ for model in
        (ub.User, ub.Shelf, ub.BookShelf, ub.KoboSyncedBooks, ub.ArchivedBook, ub.RemoteAuthToken)])
    with Session(engine) as session:
        session.add_all([ub.User(id=1, name='reader', email='reader@example.test'), ub.User(id=2, name='other', email='other@example.test')])
        session.commit()
        monkeypatch.setattr(ub, 'session', session)
        yield session
    engine.dispose()


def test_membership_is_private_idempotent_and_visible_to_legacy_sync(database):
    old = ub.Shelf(user_id=1, name='Existing Kobo shelf', kobo_sync=True)
    unrelated = ub.Shelf(user_id=2, name='Send to Kobo', kobo_sync=True)
    database.add_all([old, unrelated]); database.commit()
    before = datetime.now() - timedelta(seconds=1)
    assert delivery.enqueue(1, 42) is False
    assert delivery.enqueue(1, 42) is False
    shelves = database.query(ub.Shelf).filter_by(user_id=1).all()
    assert len(shelves) == 2
    managed = next(s for s in shelves if s.id != old.id)
    assert managed.is_public == 0 and managed.kobo_sync
    # The original Kobo inclusion/deletion queries see this membership unchanged.
    allowed = database.query(ub.BookShelf).join(ub.Shelf).filter(
        ub.Shelf.user_id == 1, ub.Shelf.kobo_sync == True).all()
    assert len(allowed) == 1 and allowed[0].book_id == 42
    assert allowed[0].date_added > before
    assert database.query(ub.BookShelf).filter_by(shelf=unrelated.id).count() == 0
    managed.name = 'My renamed device shelf'; database.commit()
    delivery.enqueue(1, 43)
    assert database.query(ub.Shelf).filter_by(user_id=1).count() == 2


def test_unarchive_only_requested_users_book_and_keep_existing_synced_state(database):
    database.add_all([ub.KoboSyncedBooks(user_id=1, book_id=42),
                      ub.KoboSyncedBooks(user_id=2, book_id=42),
                      ub.ArchivedBook(user_id=1, book_id=42, is_archived=True),
                      ub.ArchivedBook(user_id=2, book_id=42, is_archived=True)])
    database.commit()
    assert delivery.enqueue(1, 42) is False
    assert not database.query(ub.ArchivedBook).filter_by(user_id=1).one().is_archived
    assert database.query(ub.ArchivedBook).filter_by(user_id=2).one().is_archived
    assert database.query(ub.KoboSyncedBooks).one().user_id == 2
    database.add(ub.KoboSyncedBooks(user_id=1, book_id=42)); database.commit()
    assert delivery.enqueue(1, 42) is True
    assert database.query(ub.KoboSyncedBooks).count() == 2


def test_disabled_or_public_delivery_shelf_is_not_silently_reenabled(database):
    delivery.enqueue(1, 42)
    shelf = database.query(ub.Shelf).one()
    shelf.kobo_sync = False; database.commit()
    with pytest.raises(ValueError):
        delivery.enqueue(1, 43)
    assert not shelf.kobo_sync
    assert database.query(ub.BookShelf).count() == 1


def test_configured_is_per_user_and_requires_download_rights(database):
    user = SimpleNamespace(id=1, is_authenticated=True, role_download=lambda: True)
    token = ub.RemoteAuthToken(); token.user_id = 2; token.token_type = 1
    database.add(token); database.commit()
    assert not delivery.configured(user, True)
    token.user_id = 1; database.commit()
    assert delivery.configured(user, True)
    assert not delivery.configured(user, False)
    user.role_download = lambda: False
    assert not delivery.configured(user, True)


@pytest.mark.parametrize('book, configured, status', [
    (None, True, 404),
    (SimpleNamespace(data=[SimpleNamespace(format='PDF')]), True, 400),
    (None, False, 403),
])
def test_route_rejects_hidden_books_unsupported_formats_and_unconfigured_users(monkeypatch, book, configured, status):
    from cps import web
    monkeypatch.setattr(delivery, 'configured', lambda *_: configured)
    monkeypatch.setattr(delivery, 'enqueue', lambda *_: pytest.fail('must not queue rejected requests'))
    monkeypatch.setattr(web, 'calibre_db', SimpleNamespace(get_filtered_book=lambda *a, **kw: book))
    monkeypatch.setattr(web, 'config', SimpleNamespace(config_kobo_sync=True))
    app = Flask(__name__); Babel(app)
    with app.test_request_context('/book/42/send-to-kobo', method='POST'):
        try:
            result = unwrap(web.send_to_kobo)(42)
            assert result[1] == status
        except HTTPException as error:
            assert error.code == status


def test_http_route_requires_login_download_permission_and_csrf(monkeypatch):
    from cps import web, usermanagement
    from cps.cw_login import LoginManager
    from flask_wtf.csrf import CSRFProtect, generate_csrf
    user = SimpleNamespace(id=1, is_authenticated=True, is_active=True,
                           is_anonymous=False, role_download=lambda: False)
    app = Flask(__name__)
    app.config['SECRET_KEY'] = 'isolated-test-secret'
    Babel(app)
    manager = LoginManager(app)
    manager.user_loader(lambda *_: user)
    CSRFProtect(app)
    monkeypatch.setattr(usermanagement, 'config', SimpleNamespace(config_allow_reverse_proxy_header_login=False))
    monkeypatch.setattr(web, 'config', SimpleNamespace(config_kobo_sync=True))
    monkeypatch.setattr(delivery, 'configured', lambda *_: True)
    monkeypatch.setattr(web, 'calibre_db', SimpleNamespace(get_filtered_book=lambda *a, **kw:
        SimpleNamespace(data=[SimpleNamespace(format='EPUB')])))
    calls = []
    monkeypatch.setattr(delivery, 'enqueue', lambda user_id, book_id: calls.append((user_id, book_id)) or False)
    app.add_url_rule('/csrf', view_func=lambda: generate_csrf())
    app.add_url_rule('/book/<int:book_id>/send-to-kobo', view_func=web.send_to_kobo, methods=['POST'])
    client = app.test_client()
    token = client.get('/csrf').text
    url = '/book/42/send-to-kobo'
    assert client.get(url).status_code == 405
    assert client.post(url, data={'csrf_token': token}).status_code == 401
    with client.session_transaction() as session:
        session['_user_id'] = '1'
        session['_fresh'] = True
        session['_random'] = 'test-random'
        session['_id'] = 'test-session'
    assert client.post(url).status_code == 400
    assert client.post(url, data={'csrf_token': token}).status_code == 403
    user.role_download = lambda: True
    response = client.post(url, data={'csrf_token': token, 'user_id': 2},
                           headers={'X-Requested-With': 'XMLHttpRequest'})
    assert response.status_code == 200
    assert 'Sync your Kobo' in response.json['message']
    assert calls == [(1, 42)]
