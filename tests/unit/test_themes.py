"""Focused tests for the incremental upstream-compatible theme slice."""

from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit

import pytest
from flask import Flask, g

from cps import themes
from cps.render_template import themed_render


def test_theme_lookup_falls_back_safely_and_forces_basic_to_simple():
    assert themes.get_theme("not-a-theme") is themes.DEFAULT_THEME
    assert themes.get_theme(999)["identifier"] == "standard"
    assert themes.get_theme_identifier(1, "basic") == "simple"
    assert themes.get_theme_identifier(1, "web") == "caliblur"
    assert themes.is_valid_theme(0)
    assert not themes.is_valid_theme(2)
    assert not themes.is_valid_theme("invalid")


def test_theme_normalization_allows_user_themes_but_not_internal_views():
    assert themes.normalize_theme_id(0) == 0
    assert themes.normalize_theme_id("1") == 1
    assert themes.normalize_theme_id(2) == themes.CONFIG_DEFAULT_THEME_ID
    assert themes.normalize_theme_id("invalid", fallback=0) == 0
    assert themes.normalize_theme_id(None, fallback="invalid") == themes.CONFIG_DEFAULT_THEME_ID


def test_theme_template_path_rejects_traversal():
    assert themes.template_path("simple", "basic_index.html") == "simple/templates/basic_index.html"
    for name in ("../layout.html", "/layout.html", "nested\\layout.html"):
        try:
            themes.template_path("simple", name)
        except ValueError:
            pass
        else:
            raise AssertionError("unsafe template path was accepted")


def test_theme_helper_prefers_existing_theme_template_and_falls_back(tmp_path):
    from jinja2 import ChoiceLoader, FileSystemLoader

    (tmp_path / "standard" / "templates").mkdir(parents=True)
    (tmp_path / "standard" / "templates" / "modal.html").write_text(
        "standard modal", encoding="utf-8"
    )
    (tmp_path / "flat.html").write_text("flat", encoding="utf-8")
    app = Flask(__name__, template_folder=str(tmp_path))
    app.jinja_loader = ChoiceLoader([FileSystemLoader(str(tmp_path))])

    with app.test_request_context("/"):
        g.current_theme = 0
        assert themes.resolve_template("modal.html") == "standard/templates/modal.html"
        assert themes.resolve_template("flat.html") == "flat.html"


def test_upstream_style_theme_extends_resolve_through_themed_loader(tmp_path):
    from jinja2 import ChoiceLoader, FileSystemLoader

    standard_templates = tmp_path / "standard" / "templates"
    standard_templates.mkdir(parents=True)
    (standard_templates / "layout.html").write_text(
        "header{% block body %}{% endblock %}", encoding="utf-8"
    )
    (standard_templates / "index.html").write_text(
        '{% extends theme("layout.html") %}{% block body %}themed{% endblock %}',
        encoding="utf-8",
    )
    app = Flask(__name__, template_folder=str(tmp_path))
    app.jinja_loader = ChoiceLoader([FileSystemLoader(str(tmp_path))])
    app.jinja_env.globals["theme"] = themes.resolve_template

    with app.test_request_context("/"):
        g.current_theme = 0
        assert themed_render("index.html") == "headerthemed"


def test_theme_render_falls_back_to_flat_loader(tmp_path):
    (tmp_path / "fallback.html").write_text("flat fallback", encoding="utf-8")
    app = Flask(__name__, template_folder=str(tmp_path))
    with app.test_request_context("/"):
        g.current_theme = 2
        assert themed_render("fallback.html") == "flat fallback"


def test_basic_index_renders_simple_template():
    from pathlib import Path
    from jinja2 import ChoiceLoader, FileSystemLoader
    from cps.jinjia import shortentitle_filter

    app = Flask(__name__, template_folder=str(Path(__file__).parents[2] / "cps" / "templates"))
    app.jinja_loader = ChoiceLoader([
        FileSystemLoader(str(Path(__file__).parents[2] / "cps" / "themes")),
        app.jinja_loader,
    ])
    app.jinja_env.globals["_"] = lambda value: value
    app.jinja_env.filters["shortentitle"] = shortentitle_filter
    app.jinja_env.globals["current_user"] = SimpleNamespace(
        locale="en", is_authenticated=False, is_anonymous=True
    )
    app.add_url_rule("/basic", endpoint="basic.index", view_func=lambda: "")
    app.add_url_rule("/", endpoint="web.index", view_func=lambda: "")

    with app.test_request_context("/basic"):
        g.allow_anonymous = True
        rendered = themed_render(
            "basic_index.html",
            theme_id=2,
            instance="Test Library",
            title="Search",
            searchterm="",
            entries=[],
            pagination=SimpleNamespace(has_prev=False, has_next=False),
        )

    assert "Test Library" in rendered
    assert "No Results Found" in rendered
    assert "caliBlur" not in rendered


@pytest.mark.parametrize("destination_page", [1, 3])
def test_other_page_url_uses_destination_page_in_query(destination_page):
    from cps.jinjia import url_for_other_page

    app = Flask(__name__)
    app.add_url_rule("/basic", endpoint="basic.index", view_func=lambda: "")

    with app.test_request_context("/basic?page=2&query=history"):
        generated = urlsplit(url_for_other_page(destination_page))

    assert generated.path == "/basic"
    assert parse_qs(generated.query) == {
        "page": [str(destination_page)],
        "query": ["history"],
    }


def test_other_page_url_uses_destination_page_for_path_parameter():
    from cps.jinjia import url_for_other_page

    app = Flask(__name__)
    app.add_url_rule("/basic/<int:page>", endpoint="basic.index", view_func=lambda page: "")

    with app.test_request_context("/basic/2?page=2&query=history"):
        assert url_for_other_page(1) == "/basic/1?query=history"
        assert url_for_other_page(3) == "/basic/3?query=history"


def test_pastel_is_configurable_and_basic_still_uses_simple():
    assert themes.normalize_theme_id("3") == 3
    assert themes.get_theme_identifier(3, "basic") == "simple"
    assert [theme["id"] for theme in themes.get_available_themes()] == [0, 1, 3]


@pytest.mark.parametrize("kobo_enabled", [False, True])
@pytest.mark.parametrize("mail_settings", [("", False), ("first@example.test,second@example.test", False)])
@pytest.mark.parametrize("theme_id", [0, 1, 3])
@pytest.mark.parametrize("is_xhr", [False, True])
@pytest.mark.parametrize("has_description", [False, True])
def test_book_description_order_and_actions_survive_theme_inheritance(theme_id, is_xhr, has_description, mail_settings, kobo_enabled):
    from datetime import datetime
    from pathlib import Path
    from unittest.mock import Mock

    from flask_babel import Babel
    from jinja2 import ChoiceLoader, DictLoader, FileSystemLoader
    from cps.jinjia import jinjia

    app = Flask(__name__)
    Babel(app)
    app.register_blueprint(jinjia)
    # Render the production detail body through both full-page and XHR parents.
    shell = ('{% from theme("modal_dialogs.html") import delete_book %}'
             '{% block header %}{% endblock %}{% block body %}{% endblock %}')
    app.jinja_loader = ChoiceLoader([
        DictLoader({'layout.html': shell}),
        FileSystemLoader(str(Path(__file__).parents[2] / 'cps/themes')),
        FileSystemLoader(str(Path(__file__).parents[2] / 'cps/templates')),
    ])
    user = Mock()
    user.is_anonymous = False
    user.is_authenticated = True
    user.kindle_mail, user.allow_additional_ereader_emails = mail_settings
    user.role_download.return_value = True
    user.role_viewer.return_value = True
    user.role_edit.return_value = False
    user.check_visibility.return_value = False
    user.shelf.all.return_value = []
    app.jinja_env.globals.update(
        current_user=user, theme=themes.resolve_template,
        _=lambda value, **kwargs: value % kwargs if kwargs else value,
        url_for=lambda endpoint, **kwargs: '/' + endpoint,
        csrf_token=lambda: 'test-token',
    )
    entry = SimpleNamespace(
        id=42, title='A Quiet Garden', ordered_authors=[], ratings=[], series=[],
        uuid='test-uuid', timestamp=datetime(2026, 1, 1), last_modified=datetime(2026, 1, 1),
        data=[SimpleNamespace(format='EPUB', uncompressed_size=1024)],
        languages=[], identifiers=[], tags=[], publishers=[], pubdate=datetime(2020, 5, 1),
        comments=[SimpleNamespace(text='<p>Garden synopsis</p><script>alert(1)</script>')] if has_description else [],
        read_status=False, is_archived=False,
        kobo_delivery_enabled=kobo_enabled, kobo_delivery_compatible=True,
        email_share_list=[{'format':'Epub', 'convert':0, 'text':'EPUB'}],
    )
    with app.test_request_context('/'):
        g.current_theme = theme_id
        g.theme = themes.get_theme(theme_id)
        g.shelves_access = []
        rendered = themed_render(
            'detail.html', entry=entry, title='Book Details', is_xhr=is_xhr,
            cc=[], books_shelfs=[], audioentries=[], reader_list=['epub'],
        )
    if kobo_enabled:
        assert 'id="sendToKoboBtn"' in rendered
    if mail_settings[0]:
        assert 'id="sendToEReaderBtn"' in rendered
    if theme_id == 3:
        assert 'pastel-book-navigation' in rendered
        assert rendered.index('pastel-book-navigation') < rendered.index('book-detail-main', rendered.index('<div class="single'))
        assert rendered.index('book-publication-date') < rendered.index('id="detail-rating-block"')
        assert 'publishing-date meta-chip' not in rendered
        assert 'glyphicon-envelope' not in rendered
        assert ('Close book' if is_xhr else 'Back to library') in rendered
        if kobo_enabled:
            assert 'id="sendToKoboBtn"' in rendered
        if mail_settings[0]:
            assert 'id="sendToEReaderBtn"' in rendered
            assert 'id="emailSelectModal"' in rendered
            assert 'data-direct-send="true"' not in rendered
            assert 'id="custom_emails"' not in rendered
            recipients = [line for line in rendered.splitlines() if 'name="selected_emails"' in line]
            assert len(recipients) == 2 and all('checked' not in line for line in recipients)
        else:
            assert '/web.profile' in rendered
    assert 'web.download_link' in rendered
    assert 'id="have_read_form"' in rendered
    assert '<script>alert(1)</script>' not in rendered
    if has_description:
        assert rendered.count('id="decription"') == 1
        description = rendered.index('id="decription"')
        metadata = rendered.index('class="book-metadata"')
        assert (description < metadata) == (theme_id == 3)
    else:
        assert 'id="decription"' not in rendered


def test_http_error_before_theme_initialization():
    from pathlib import Path
    from flask import render_template
    app = Flask(__name__, template_folder=str(Path(__file__).parents[2] / 'cps/templates'))
    app.jinja_env.globals['_'] = lambda value: value
    app.jinja_env.globals['url_for'] = lambda *args, **kwargs: '/home'
    with app.test_request_context('/'):
        assert not hasattr(g, 'theme')
        rendered = render_template('http_error.html', instance='Library', error_code='Error 400',
                                   error_name='Bad Request', issue=False, unconfigured=False)
    assert 'Error 400' in rendered
    assert 'Bad Request' in rendered
