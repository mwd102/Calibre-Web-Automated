"""Regression tests for filtered book access in web and Kobo endpoints."""

from datetime import datetime, timezone
from inspect import unwrap
from types import SimpleNamespace

import pytest
from flask import Flask
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from cps import db, ub


@pytest.fixture
def filtered_book_db(monkeypatch):
    """Provide the Calibre/app tables needed by ``common_filters``."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    with engine.begin() as connection:
        # Calibre's format table is attached in production.  The complete
        # Calibre metadata is created here because Books uses subquery-loaded
        # relationships, even when the test only selects a book.
        connection.execute(text("ATTACH DATABASE ':memory:' AS calibre"))
        db.Base.metadata.create_all(connection)
        ub.Base.metadata.create_all(
            connection,
            tables=[ub.User.__table__, ub.ArchivedBook.__table__],
        )
    session = sessionmaker(bind=engine, future=True, expire_on_commit=False)()

    user = ub.User(name="reader", default_language="all")
    session.add(user)
    session.flush()

    tags = {name: db.Tags(name) for name in ("allowed", "hidden")}
    languages = {code: db.Languages(code) for code in ("eng", "fra")}
    session.add_all([*tags.values(), *languages.values()])
    session.flush()

    def add_book(book_uuid, language, tag, title=None):
        now = datetime.now(timezone.utc)
        book = db.Books(
            title or book_uuid,
            title or book_uuid,
            title or book_uuid,
            now,
            now,
            "1.0",
            now,
            book_uuid,
            False,
            [],
            [],
        )
        book.uuid = book_uuid
        book.languages = [languages[language]]
        book.tags = [tags[tag]]
        session.add(book)
        session.flush()
        return book

    books = {
        "allowed": add_book("uuid-allowed", "eng", "allowed"),
        "hidden_tag": add_book("uuid-hidden-tag", "eng", "hidden"),
        "wrong_language": add_book("uuid-wrong-language", "fra", "allowed"),
        "archived": add_book("uuid-archived", "eng", "allowed"),
    }
    session.add(ub.ArchivedBook(user_id=user.id, book_id=books["archived"].id, is_archived=True))
    session.commit()

    user.default_language = "eng"
    user.denied_tags = "hidden"
    monkeypatch.setattr(db, "current_user", user)
    monkeypatch.setattr(ub, "session", session)

    calibre_db = db.CalibreDB()
    calibre_db.session = session
    calibre_db.config = SimpleNamespace(config_restricted_column=False)

    yield calibre_db, user, books

    session.close()
    engine.dispose()


@pytest.mark.unit
def test_get_book_by_uuid_allows_book_passing_visibility_filters(filtered_book_db):
    calibre_db, _user, _books = filtered_book_db

    book = calibre_db.get_book_by_uuid("uuid-allowed")

    assert book is not None
    assert book.uuid == "uuid-allowed"


@pytest.mark.unit
@pytest.mark.parametrize(
    "uuid, reason",
    [
        ("uuid-hidden-tag", "denied tag"),
        ("uuid-wrong-language", "language restriction"),
        ("uuid-archived", "archived book"),
    ],
)
def test_get_book_by_uuid_hides_restricted_books(filtered_book_db, uuid, reason):
    calibre_db, _user, _books = filtered_book_db

    assert calibre_db.get_book_by_uuid(uuid) is None, reason


@pytest.mark.unit
def test_serve_book_fails_closed_when_book_is_filtered(monkeypatch):
    """A filtered-out book must not reach format or filesystem lookup."""
    from cps import web

    calibre_db = SimpleNamespace(
        get_filtered_book=lambda _book_id: None,
        get_book_format=lambda *_args: pytest.fail("format lookup must not run"),
    )
    monkeypatch.setattr(web, "calibre_db", calibre_db)

    app = Flask(__name__)
    with app.test_request_context("/show/42/EPUB"):
        result = unwrap(web.serve_book)(42, "EPUB", "None")

    assert result == "File not in Database"
