# Calibre-Web Automated – fork of Calibre-Web
# SPDX-License-Identifier: GPL-3.0-or-later
"""Regression tests for FK-safe application database cleanup paths."""

import pytest
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker

from cps import db_cleanup, ub


@pytest.fixture
def app_session(tmp_path):
    engine = create_engine("sqlite:///{}".format(tmp_path / "app.db"))

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(connection, _record):
        connection.execute("PRAGMA foreign_keys=ON")

    ub.Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def _assert_fk_clean(session):
    assert session.execute(text("PRAGMA foreign_key_check")).all() == []


@pytest.mark.unit
def test_delete_shelf_rows_removes_books_and_opds_exposures(app_session):
    owner = ub.User(name="owner", email="owner@example.invalid")
    viewer = ub.User(name="viewer", email="viewer@example.invalid")
    shelf = ub.Shelf(name="Shared", user=owner)
    app_session.add_all([owner, viewer, shelf])
    app_session.flush()
    app_session.add_all([
        ub.BookShelf(ub_shelf=shelf, book_id=12),
        ub.OpdsShelfExposure(user_id=viewer.id, shelf_id=shelf.id),
    ])
    app_session.commit()

    db_cleanup.delete_shelf_rows(app_session, shelf.id)
    app_session.commit()

    assert app_session.query(ub.Shelf).count() == 0
    assert app_session.query(ub.BookShelf).count() == 0
    assert app_session.query(ub.OpdsShelfExposure).count() == 0
    _assert_fk_clean(app_session)


@pytest.mark.unit
def test_delete_kobo_states_removes_both_child_models(app_session):
    user = ub.User(name="reader", email="reader@example.invalid")
    app_session.add(user)
    app_session.flush()
    state = ub.KoboReadingState(user_id=user.id, book_id=23)
    state.current_bookmark = ub.KoboBookmark(location_value="chapter-1")
    state.statistics = ub.KoboStatistics(spent_reading_minutes=5)
    app_session.add(state)
    app_session.commit()

    db_cleanup.delete_kobo_reading_states(app_session)
    app_session.commit()

    assert app_session.query(ub.KoboReadingState).count() == 0
    assert app_session.query(ub.KoboBookmark).count() == 0
    assert app_session.query(ub.KoboStatistics).count() == 0
    _assert_fk_clean(app_session)


@pytest.mark.unit
def test_delete_user_rows_removes_real_model_dependency_graph(app_session):
    user = ub.User(name="departing", email="departing@example.invalid")
    other = ub.User(name="remaining", email="remaining@example.invalid")
    shelf = ub.Shelf(name="Shelf", user=user)
    magic = ub.MagicShelf(name="Magic", user=user)
    app_session.add_all([user, other, shelf, magic])
    app_session.flush()
    state = ub.KoboReadingState(user_id=user.id, book_id=42)
    state.current_bookmark = ub.KoboBookmark(location_value="end")
    state.statistics = ub.KoboStatistics(spent_reading_minutes=10)
    app_session.add_all([
        ub.BookShelf(ub_shelf=shelf, book_id=42),
        ub.OpdsShelfExposure(user_id=other.id, shelf_id=shelf.id),
        ub.MagicShelfCache(shelf_id=magic.id, user_id=user.id, book_ids=[42]),
        ub.OpdsMagicShelfExposure(user_id=other.id, shelf_id=magic.id),
        ub.HiddenMagicShelfTemplate(user_id=other.id, shelf_id=magic.id),
        ub.DismissedDuplicateGroup(user_id=user.id, group_hash="abc"),
        ub.ShelfArchive(user_id=user.id, uuid="archive"),
        ub.ReadBook(user_id=user.id, book_id=42),
        ub.Downloads(user_id=user.id, book_id=42),
        ub.Bookmark(user_id=user.id, book_id=42),
        ub.ArchivedBook(user_id=user.id, book_id=42),
        ub.KoboSyncedBooks(user_id=user.id, book_id=42),
        ub.KoboAnnotationSync(user_id=user.id, annotation_id="a", book_id=42),
        ub.User_Sessions(user.id, "session", "random", 1),
        state,
    ])
    token = ub.RemoteAuthToken()
    token.user_id = user.id
    app_session.add(token)
    app_session.commit()

    db_cleanup.delete_user_rows(app_session, user.id)
    app_session.commit()

    assert app_session.query(ub.User).all() == [other]
    for model in (
        ub.Shelf, ub.MagicShelf, ub.BookShelf, ub.OpdsShelfExposure,
        ub.MagicShelfCache, ub.OpdsMagicShelfExposure,
        ub.HiddenMagicShelfTemplate, ub.KoboReadingState, ub.KoboBookmark,
        ub.KoboStatistics, ub.ReadBook, ub.Downloads, ub.Bookmark,
        ub.ArchivedBook, ub.KoboSyncedBooks, ub.KoboAnnotationSync,
        ub.ShelfArchive, ub.DismissedDuplicateGroup, ub.RemoteAuthToken,
        ub.User_Sessions,
    ):
        assert app_session.query(model).count() == 0, model.__name__
    _assert_fk_clean(app_session)
