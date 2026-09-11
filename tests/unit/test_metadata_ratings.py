"""Regression tests for automatic metadata rating updates."""

from datetime import datetime
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from cps import db, metadata_helper


class _MetadataSettings:
    """Enable only rating updates so these tests isolate the rating path."""

    @staticmethod
    def get_cwa_settings():
        return {
            "auto_metadata_smart_application": False,
            "auto_metadata_update_title": False,
            "auto_metadata_update_authors": False,
            "auto_metadata_update_description": False,
            "auto_metadata_update_publisher": False,
            "auto_metadata_update_tags": False,
            "auto_metadata_update_series": False,
            "auto_metadata_update_published_date": False,
            "auto_metadata_update_rating": True,
            "auto_metadata_update_identifiers": False,
            "auto_metadata_update_cover": False,
        }


@pytest.fixture
def calibre_session(monkeypatch):
    """Provide the minimal Calibre schema needed by the metadata helper."""
    engine = create_engine("sqlite:///:memory:")
    db.Base.metadata.create_all(
        engine,
        tables=[db.Books.__table__, db.Ratings.__table__, db.books_ratings_link],
    )
    session = sessionmaker(bind=engine, future=True, expire_on_commit=False)()
    calibre_db = db.CalibreDB.__new__(db.CalibreDB)
    calibre_db.session = session
    monkeypatch.setattr(metadata_helper, "CWA_DB", _MetadataSettings)
    yield session, calibre_db
    session.close()
    engine.dispose()


def _book(title):
    return db.Books(
        title,
        title,
        title,
        datetime(2026, 1, 1),
        datetime(2026, 1, 1),
        "1.0",
        datetime(2026, 1, 1),
        title,
        False,
        [],
        [],
    )


def test_metadata_rating_reuses_row_without_mutating_shared_rating(calibre_session):
    session, calibre_db = calibre_session
    shared_rating = db.Ratings(rating=8)
    replacement_rating = db.Ratings(rating=6)
    first_book = _book("First")
    second_book = _book("Second")
    first_book.ratings = [shared_rating]
    second_book.ratings = [shared_rating]
    session.add_all([replacement_rating, first_book, second_book])
    session.commit()

    assert metadata_helper._apply_metadata_to_book(
        first_book, SimpleNamespace(rating=3), calibre_db
    ) is True

    assert first_book.ratings[0].rating == 6
    assert first_book.ratings[0].id == replacement_rating.id
    assert second_book.ratings[0].rating == 8
    assert session.query(db.Ratings).filter_by(rating=8).count() == 1
    links = session.execute(db.books_ratings_link.select()).all()
    assert (first_book.id, replacement_rating.id) in links
    assert (second_book.id, shared_rating.id) in links


def test_metadata_rating_creates_row_for_new_value(calibre_session):
    session, calibre_db = calibre_session
    shared_rating = db.Ratings(rating=8)
    first_book = _book("First")
    second_book = _book("Second")
    first_book.ratings = [shared_rating]
    second_book.ratings = [shared_rating]
    session.add_all([first_book, second_book])
    session.commit()

    assert metadata_helper._apply_metadata_to_book(
        first_book, SimpleNamespace(rating=2.5), calibre_db
    ) is True

    assert first_book.ratings[0].rating == 5
    assert session.query(db.Ratings).filter_by(rating=5).count() == 1
    assert second_book.ratings[0].rating == 8
    links = session.execute(db.books_ratings_link.select()).all()
    assert (first_book.id, first_book.ratings[0].id) in links
    assert (second_book.id, shared_rating.id) in links
