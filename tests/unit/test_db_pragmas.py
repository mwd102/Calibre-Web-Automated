# Calibre-Web Automated – fork of Calibre-Web
# Copyright (C) 2018-2026 Calibre-Web contributors
# Copyright (C) 2024-2026 Calibre-Web Automated contributors
# SPDX-License-Identifier: GPL-3.0-or-later
# See CONTRIBUTORS for full list of authors.

"""Tests for connection-scoped SQLite foreign-key enforcement."""

import sqlite3

import pytest
from sqlalchemy import create_engine, event, text
from sqlalchemy.pool import StaticPool

from cps.db_pragmas import enable_sqlite_foreign_keys

METADATA_SCHEMA = """
CREATE TABLE books (id INTEGER PRIMARY KEY, title TEXT);
CREATE TABLE books_pages_link (
    book INTEGER PRIMARY KEY,
    pages INTEGER DEFAULT 0 NOT NULL,
    FOREIGN KEY (book) REFERENCES books(id) ON DELETE CASCADE
);
CREATE TABLE book_format_checksums (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    book INTEGER NOT NULL,
    format TEXT NOT NULL COLLATE NOCASE,
    checksum TEXT NOT NULL,
    FOREIGN KEY (book) REFERENCES books(id) ON DELETE CASCADE
);
CREATE TRIGGER books_pages_link_create_trigger AFTER INSERT ON books FOR EACH ROW
BEGIN
    INSERT INTO books_pages_link(book) VALUES(NEW.id);
END;
"""

APP_SCHEMA = """
CREATE TABLE user (id INTEGER PRIMARY KEY, name TEXT NOT NULL);
CREATE TABLE kosync_progress (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    document TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES user(id) ON DELETE CASCADE
);
"""


def _create_database(path, schema):
    with sqlite3.connect(path) as connection:
        connection.executescript(schema)


def _attached_engine(tmp_path, with_pragma=True):
    metadata_db = tmp_path / "metadata.db"
    app_db = tmp_path / "app.db"
    _create_database(metadata_db, METADATA_SCHEMA)
    _create_database(app_db, APP_SCHEMA)

    # This mirrors CalibreDB: the application uses one in-memory SQLAlchemy
    # engine and attaches both on the same DBAPI connection.
    engine = create_engine(
        "sqlite://",
        isolation_level="SERIALIZABLE",
        connect_args={"check_same_thread": False, "timeout": 30},
        poolclass=StaticPool,
    )
    if with_pragma:
        enable_sqlite_foreign_keys(engine)
    with engine.begin() as connection:
        connection.execute(text("ATTACH DATABASE :metadata AS calibre"),
                           {"metadata": str(metadata_db)})
        connection.execute(text("ATTACH DATABASE :app AS app_settings"),
                           {"app": str(app_db)})
    return engine


def _foreign_key_violations(connection, schema):
    """Read-only diagnostic equivalent to the production SQLite check."""
    return list(connection.execute(text(f"PRAGMA {schema}.foreign_key_check")))


@pytest.mark.unit
class TestEnableSqliteForeignKeys:
    def test_is_enabled_for_main_and_attached_databases(self, tmp_path):
        engine = _attached_engine(tmp_path)
        try:
            # The pragma is connection-wide: both attached databases use it.
            with engine.begin() as connection:
                assert connection.execute(text("PRAGMA foreign_keys")).scalar() == 1
                connection.execute(text(
                    "INSERT INTO calibre.books (id, title) VALUES (1, 'Book')"
                ))
                connection.execute(text(
                    "INSERT INTO calibre.book_format_checksums "
                    "(book, format, checksum) VALUES (1, 'EPUB', 'checksum')"
                ))
                connection.execute(text(
                    "INSERT INTO app_settings.user (id, name) VALUES (1, 'reader')"
                ))
                connection.execute(text(
                    "INSERT INTO app_settings.kosync_progress "
                    "(user_id, document) VALUES (1, 'document')"
                ))
            with engine.begin() as connection:
                connection.execute(text("DELETE FROM calibre.books WHERE id = 1"))
                connection.execute(text("DELETE FROM app_settings.user WHERE id = 1"))

            with engine.connect() as connection:
                assert connection.execute(text(
                    "SELECT COUNT(*) FROM calibre.book_format_checksums"
                )).scalar() == 0
                assert connection.execute(text(
                    "SELECT COUNT(*) FROM calibre.books_pages_link"
                )).scalar() == 0
                assert connection.execute(text(
                    "SELECT COUNT(*) FROM app_settings.kosync_progress"
                )).scalar() == 0
                assert _foreign_key_violations(connection, "calibre") == []
                assert _foreign_key_violations(connection, "app_settings") == []
        finally:
            engine.dispose()

    def test_without_helper_leaves_orphans_and_reports_them(self, tmp_path):
        engine = _attached_engine(tmp_path, with_pragma=False)
        try:
            with engine.begin() as connection:
                connection.execute(text(
                    "INSERT INTO calibre.books (id, title) VALUES (1, 'Book')"
                ))
                connection.execute(text(
                    "INSERT INTO calibre.book_format_checksums "
                    "(book, format, checksum) VALUES (1, 'EPUB', 'checksum')"
                ))
                connection.execute(text(
                    "INSERT INTO app_settings.user (id, name) VALUES (1, 'reader')"
                ))
                connection.execute(text(
                    "INSERT INTO app_settings.kosync_progress "
                    "(user_id, document) VALUES (1, 'document')"
                ))
            with engine.begin() as connection:
                connection.execute(text("DELETE FROM calibre.books WHERE id = 1"))
                connection.execute(text("DELETE FROM app_settings.user WHERE id = 1"))
            with engine.connect() as connection:
                assert connection.execute(text(
                    "SELECT COUNT(*) FROM calibre.book_format_checksums"
                )).scalar() == 1
                assert connection.execute(text(
                    "SELECT COUNT(*) FROM app_settings.kosync_progress"
                )).scalar() == 1
                assert len(_foreign_key_violations(connection, "calibre")) == 2
                assert len(_foreign_key_violations(connection, "app_settings")) == 1
        finally:
            engine.dispose()

    def test_listener_does_not_replace_existing_connection_pragmas(self, tmp_path):
        engine = create_engine("sqlite://", poolclass=StaticPool)

        @event.listens_for(engine, "connect")
        def set_existing_pragma(dbapi_connection, connection_record):
            dbapi_connection.execute("PRAGMA busy_timeout=4321")

        enable_sqlite_foreign_keys(engine)
        try:
            with engine.connect() as connection:
                assert connection.execute(text("PRAGMA foreign_keys")).scalar() == 1
                assert connection.execute(text("PRAGMA busy_timeout")).scalar() == 4321
        finally:
            engine.dispose()

    def test_listener_runs_again_for_new_database_connections(self, tmp_path):
        db = tmp_path / "standalone.db"
        engine = create_engine(f"sqlite:///{db}", connect_args={"timeout": 30})
        enable_sqlite_foreign_keys(engine)
        try:
            for _ in range(2):
                with engine.connect() as connection:
                    assert connection.execute(text("PRAGMA foreign_keys")).scalar() == 1
                engine.dispose()
        finally:
            engine.dispose()
