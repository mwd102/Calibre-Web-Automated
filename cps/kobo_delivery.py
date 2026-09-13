"""One-click delivery through the existing, backwards-compatible Kobo shelves."""
from datetime import datetime, timezone
from uuid import NAMESPACE_URL, uuid5

from sqlalchemy import func

from . import ub


def configured(user, enabled):
    """Check token existence only; never load or expose a device credential."""
    return bool(enabled and user.is_authenticated and user.role_download() and
                ub.session.query(ub.RemoteAuthToken.id).filter_by(
                    user_id=user.id, token_type=1).first())


def compatible(book):
    return any(data.format.upper() in ('EPUB', 'KEPUB') for data in book.data)


def enqueue(user_id, book_id):
    """Caller enforces authentication, download rights and book visibility.

    A stable UUID keeps renamed delivery shelves usable and avoids adopting an
    unrelated shelf with the same name. Existing manual sync shelves are untouched.
    Commit the shelf, membership and optional unarchive together.
    """
    session = ub.session
    now = datetime.now(timezone.utc)
    shelf_uuid = str(uuid5(NAMESPACE_URL, 'cwa:send-to-kobo:%s' % user_id))
    try:
        # Serialize concurrent sends for this user before checking membership.
        # This also prevents duplicate delivery shelves across worker processes.
        session.query(ub.User).filter_by(id=user_id).update(
            {ub.User.kobo_only_shelves_sync: ub.User.kobo_only_shelves_sync},
            synchronize_session=False)
        shelf = session.query(ub.Shelf).filter_by(user_id=user_id, uuid=shelf_uuid).first()
        if shelf is None:
            shelf = ub.Shelf(user_id=user_id, uuid=shelf_uuid, name='Send to Kobo',
                             is_public=0, kobo_sync=True)
            session.add(shelf)
            session.flush()
        elif shelf.is_public or not shelf.kobo_sync:
            raise ValueError('delivery_shelf_disabled')
        link = session.query(ub.BookShelf).filter_by(shelf=shelf.id, book_id=book_id).first()
        if link is None:
            order = session.query(func.max(ub.BookShelf.order)).filter_by(shelf=shelf.id).scalar() or 0
            link = ub.BookShelf(shelf=shelf.id, book_id=book_id, order=order + 1)
            shelf.books.append(link)
        link.date_added = now
        shelf.last_modified = now
        archived = session.query(ub.ArchivedBook).filter_by(user_id=user_id, book_id=book_id).first()
        if archived and archived.is_archived:
            archived.is_archived = False
            archived.last_modified = now
            session.query(ub.KoboSyncedBooks).filter_by(user_id=user_id, book_id=book_id).delete()
        already_synced = bool(session.query(ub.KoboSyncedBooks.id).filter_by(
            user_id=user_id, book_id=book_id).first())
        session.commit()
        return already_synced
    except Exception:
        session.rollback()
        raise
