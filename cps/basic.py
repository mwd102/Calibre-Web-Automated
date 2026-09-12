# -*- coding: utf-8 -*-
# Calibre-Web Automated – fork of Calibre-Web
# SPDX-License-Identifier: GPL-3.0-or-later

"""Small upstream-compatible reader-oriented view.

Only this blueprint selects the internal Simple view theme.  The existing
``web`` blueprint continues to use the flat-template fallback while honoring
the selected Standard or caliBlur theme.
"""

from flask import Blueprint, redirect, request, url_for
from flask_babel import get_locale, gettext as _

from . import config, db, isoLanguages
from . import calibre_db
from .render_template import render_theme_template
from .usermanagement import login_required_if_no_ano
from .web import get_sort_function


basic = Blueprint("basic", __name__)


@basic.route("/basic", methods=["GET"])
@login_required_if_no_ano
def index():
    term = request.args.get("query", "")
    try:
        page = max(1, int(request.args.get("page") or 1))
    except (TypeError, ValueError):
        page = 1

    limit = 15
    offset = (page - 1) * limit
    order = get_sort_function("stored", "search")
    join = db.books_series_link, db.Books.id == db.books_series_link.c.book, db.Series
    entries, result_count, pagination = calibre_db.get_search_results(
        term, config, offset, order, limit, *join
    )
    return render_theme_template(
        "basic_index.html",
        theme_id=2,
        searchterm=term,
        pagination=pagination,
        query=term,
        adv_searchterm=term,
        entries=entries,
        result_count=result_count,
        title=_("Search"),
        page="search",
        order=order[1],
    )


@basic.route("/basic_book/<int:book_id>")
@login_required_if_no_ano
def show_book(book_id):
    result = calibre_db.get_book_read_archived(
        book_id, config.config_read_column, allow_show_archived=True
    )
    if not result:
        return redirect(url_for("basic.index"))

    entry = result[0]
    for language in entry.languages:
        language.language_name = isoLanguages.get_language_name(
            get_locale(), language.lang_code
        )
    entry.ordered_authors = calibre_db.order_authors([entry])
    return render_theme_template(
        "basic_detail.html",
        theme_id=2,
        entry=entry,
        is_xhr=request.headers.get("X-Requested-With") == "XMLHttpRequest",
        title=entry.title,
        page="book",
    )
