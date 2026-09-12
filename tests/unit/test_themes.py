"""Focused tests for the incremental upstream-compatible theme slice."""

from types import SimpleNamespace

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


def test_other_page_url_keeps_query_filters_without_reusing_current_page():
    from cps.jinjia import url_for_other_page

    app = Flask(__name__)
    app.add_url_rule("/basic/<int:page>", endpoint="basic.index", view_func=lambda page: "")

    with app.test_request_context("/basic/2?page=2&query=history"):
        assert url_for_other_page(1) == "/basic/1?query=history"
        assert url_for_other_page(3) == "/basic/3?query=history"


def test_caliblur_uses_stable_detail_layout_hooks_and_styles_standard_login_card():
    from pathlib import Path

    root = Path(__file__).parents[2] / "cps"
    detail_js = (root / "static" / "js" / "caliBlur.js").read_text(encoding="utf-8")
    login_template = (root / "themes" / "caliblur" / "templates" / "login.html").read_text(
        encoding="utf-8"
    )

    assert '.book-detail-page .book-detail-main' in detail_js
    assert '$(".book-detail-card").length' not in detail_js
    assert ".caliblur-login .standard-login-card" in login_template
    assert ".caliblur-login .standard-login-title" in login_template
