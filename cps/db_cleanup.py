# -*- coding: utf-8 -*-
"""Foreign-key-safe cleanup helpers for the application database.

The caller owns the transaction so each multi-table cleanup remains atomic.
"""

from . import ub


def delete_kobo_reading_states(session, user_id=None):
    query = session.query(ub.KoboReadingState.id)
    if user_id is not None:
        query = query.filter(ub.KoboReadingState.user_id == user_id)
    state_ids = query
    session.query(ub.KoboBookmark).filter(
        ub.KoboBookmark.kobo_reading_state_id.in_(state_ids)
    ).delete(synchronize_session=False)
    session.query(ub.KoboStatistics).filter(
        ub.KoboStatistics.kobo_reading_state_id.in_(state_ids)
    ).delete(synchronize_session=False)
    states = session.query(ub.KoboReadingState)
    if user_id is not None:
        states = states.filter(ub.KoboReadingState.user_id == user_id)
    states.delete(synchronize_session=False)


def delete_shelf_rows(session, shelf_id):
    """Delete rows which reference a shelf, followed by the shelf itself."""
    session.query(ub.BookShelf).filter(ub.BookShelf.shelf == shelf_id).delete(synchronize_session=False)
    session.query(ub.OpdsShelfExposure).filter(
        ub.OpdsShelfExposure.shelf_id == shelf_id
    ).delete(synchronize_session=False)
    session.query(ub.Shelf).filter(ub.Shelf.id == shelf_id).delete(synchronize_session=False)


def delete_magic_shelf_rows(session, shelf_id):
    """Delete rows which reference a magic shelf, followed by the shelf."""
    session.query(ub.MagicShelfCache).filter(
        ub.MagicShelfCache.shelf_id == shelf_id
    ).delete(synchronize_session=False)
    session.query(ub.OpdsMagicShelfExposure).filter(
        ub.OpdsMagicShelfExposure.shelf_id == shelf_id
    ).delete(synchronize_session=False)
    session.query(ub.HiddenMagicShelfTemplate).filter(
        ub.HiddenMagicShelfTemplate.shelf_id == shelf_id
    ).delete(synchronize_session=False)
    session.query(ub.MagicShelf).filter(
        ub.MagicShelf.id == shelf_id
    ).delete(synchronize_session=False)


def delete_user_rows(session, user_id):
    """Delete every application row owned by a user in FK-safe order."""
    shelf_ids = session.query(ub.Shelf.id).filter(ub.Shelf.user_id == user_id)
    session.query(ub.BookShelf).filter(ub.BookShelf.shelf.in_(shelf_ids)).delete(synchronize_session=False)
    session.query(ub.OpdsShelfExposure).filter(
        (ub.OpdsShelfExposure.user_id == user_id) | (ub.OpdsShelfExposure.shelf_id.in_(shelf_ids))
    ).delete(synchronize_session=False)

    magic_ids = session.query(ub.MagicShelf.id).filter(ub.MagicShelf.user_id == user_id)
    session.query(ub.MagicShelfCache).filter(
        (ub.MagicShelfCache.user_id == user_id) | (ub.MagicShelfCache.shelf_id.in_(magic_ids))
    ).delete(synchronize_session=False)
    session.query(ub.OpdsMagicShelfExposure).filter(
        (ub.OpdsMagicShelfExposure.user_id == user_id) | (ub.OpdsMagicShelfExposure.shelf_id.in_(magic_ids))
    ).delete(synchronize_session=False)
    session.query(ub.HiddenMagicShelfTemplate).filter(
        (ub.HiddenMagicShelfTemplate.user_id == user_id) | (ub.HiddenMagicShelfTemplate.shelf_id.in_(magic_ids))
    ).delete(synchronize_session=False)

    delete_kobo_reading_states(session, user_id)
    for model in (
        ub.ReadBook, ub.Downloads, ub.Bookmark, ub.ArchivedBook,
        ub.KoboSyncedBooks, ub.KoboAnnotationSync, ub.ShelfArchive,
        ub.DismissedDuplicateGroup, ub.RemoteAuthToken, ub.User_Sessions,
    ):
        session.query(model).filter(model.user_id == user_id).delete(synchronize_session=False)

    if getattr(ub, "oauth_support", False):
        session.query(ub.OAuth).filter(ub.OAuth.user_id == user_id).delete(synchronize_session=False)

    session.query(ub.Shelf).filter(ub.Shelf.user_id == user_id).delete(synchronize_session=False)
    session.query(ub.MagicShelf).filter(ub.MagicShelf.user_id == user_id).delete(synchronize_session=False)
    session.query(ub.User).filter(ub.User.id == user_id).delete(synchronize_session=False)


def delete_user(session, user):
    """Delete ``user`` while retaining values needed by the request caller.

    Bulk deletion leaves the supplied ORM instance associated with the session.
    Once the transaction commits, reading an expired attribute from that deleted
    row raises ``ObjectDeletedError``.  Capture the display name first and only
    return the detached scalar value to the caller.
    """
    user_id = user.id
    user_name = user.name
    delete_user_rows(session, user_id)
    return user_name
