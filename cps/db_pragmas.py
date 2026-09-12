# Calibre-Web Automated – fork of Calibre-Web
# Copyright (C) 2018-2026 Calibre-Web contributors
# Copyright (C) 2024-2026 Calibre-Web Automated contributors
# SPDX-License-Identifier: GPL-3.0-or-later
# See CONTRIBUTORS for full list of authors.

"""Connection-level SQLite pragmas used by CWA's SQLAlchemy engines."""

import sqlite3

from sqlalchemy import event

from . import logger

log = logger.create()


def enable_sqlite_foreign_keys(engine):
    """Enable SQLite foreign-key enforcement for every connection in *engine*.

    ``PRAGMA foreign_keys`` is connection-scoped, applies to attached databases,
    and is ignored by SQLite when a transaction is already active.  Installing
    this listener means it runs on a newly-created DBAPI connection before
    SQLAlchemy starts any transaction.  The listener changes no other pragmas
    (for example, the WAL settings configured by the database setup code).

    This is intentionally enforcement-only.  It does not inspect, repair, or
    migrate existing rows.  Existing violations can be reviewed separately with
    ``PRAGMA foreign_key_check`` before enabling the application update.
    """

    @event.listens_for(engine, "connect")
    def _set_sqlite_foreign_keys(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        try:
            # Do not change isolation_level or use a SQLAlchemy Connection here:
            # this hook must remain outside any SQLAlchemy-managed transaction.
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA foreign_keys")
            enabled = cursor.fetchone()
            if not enabled or enabled[0] != 1:
                raise RuntimeError("SQLite did not enable foreign-key enforcement")
        except (sqlite3.Error, RuntimeError) as exc:
            log.warning(
                "Could not enable SQLite foreign-key enforcement (%s); "
                "ON DELETE CASCADE may not fire on this connection",
                exc,
            )
        finally:
            cursor.close()

    return engine
