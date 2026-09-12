# -*- coding: utf-8 -*-
# Calibre-Web Automated – fork of Calibre-Web
# Copyright (C) 2018-2026 Calibre-Web contributors
# Copyright (C) 2024-2026 Calibre-Web Automated contributors
# SPDX-License-Identifier: GPL-3.0-or-later
# See CONTRIBUTORS for full list of authors.

"""Regression tests for SQLite ATTACH paths containing quote characters."""

import sqlite3

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.pool import StaticPool

from cps.db import _sqlite_string_literal


@pytest.mark.unit
def test_attach_paths_with_single_quotes(tmp_path):
    metadata_db = tmp_path / "library's metadata.db"
    app_db = tmp_path / "application's app.db"

    for database in (metadata_db, app_db):
        with sqlite3.connect(database) as connection:
            connection.execute("CREATE TABLE marker (value TEXT)")

    engine = create_engine("sqlite://", poolclass=StaticPool)
    try:
        with engine.begin() as connection:
            connection.execute(text("ATTACH DATABASE '{}' AS calibre".format(
                _sqlite_string_literal(metadata_db))))
            connection.execute(text("ATTACH DATABASE '{}' AS app_settings".format(
                _sqlite_string_literal(app_db))))

            assert connection.execute(
                text("SELECT value FROM calibre.marker")
            ).fetchone() is None
            assert connection.execute(
                text("SELECT value FROM app_settings.marker")
            ).fetchone() is None
    finally:
        engine.dispose()


def test_sqlite_string_literal_escapes_quotes():
    assert _sqlite_string_literal("author's library") == "author''s library"
