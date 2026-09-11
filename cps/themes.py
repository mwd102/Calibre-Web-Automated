# -*- coding: utf-8 -*-
# Calibre-Web Automated – fork of Calibre-Web
# SPDX-License-Identifier: GPL-3.0-or-later

"""Theme metadata shared by the current renderer and the future theme loader.

This intentionally does not depend on Flask-Themes2 yet.  The registry mirrors
the identifiers and capabilities used by upstream so the template migration can
be introduced independently from the first alternate-view slice.
"""

from types import MappingProxyType


def _theme(**values):
    """Create immutable theme metadata so callers cannot alter the registry."""
    return MappingProxyType(values)


THEMES = (
    _theme(
        id=0,
        identifier="standard",
        label="Standard Theme",
        configurable=True,
        css_files=(),
        js_files=(),
        body_class="",
        show_home_shortcuts=False,
        profile_dropdown=False,
        show_upload_loader=False,
    ),
    _theme(
        id=1,
        identifier="caliblur",
        label="caliBlur! Dark Theme",
        configurable=True,
        css_files=("css/caliBlur.css", "css/caliBlur_override.css"),
        js_files=(
            "js/libs/jquery.visible.min.js",
            "js/libs/compromise.min.js",
            "js/libs/readmore.min.js",
            "js/caliBlur.js",
        ),
        body_class="blur",
        show_home_shortcuts=True,
        profile_dropdown=True,
        show_upload_loader=True,
    ),
    _theme(
        id=2,
        identifier="simple",
        label="Simple Theme",
        configurable=False,
        css_files=(),
        js_files=(),
        body_class="",
        show_home_shortcuts=False,
        profile_dropdown=False,
        show_upload_loader=False,
    ),
)

THEMES_BY_ID = {theme["id"]: theme for theme in THEMES}
THEMES_BY_IDENTIFIER = {theme["identifier"]: theme for theme in THEMES}
DEFAULT_THEME = THEMES_BY_ID[0]
SIMPLE_THEME_IDENTIFIER = THEMES_BY_ID[2]["identifier"]


def get_available_themes():
    """Return themes that are safe to expose as configurable choices."""
    return [theme for theme in THEMES if theme["configurable"]]


def get_default_theme():
    return DEFAULT_THEME


def get_theme(theme_id):
    """Return a known theme, safely falling back to upstream's standard theme."""
    try:
        theme_id = int(theme_id)
    except (TypeError, ValueError):
        return DEFAULT_THEME
    return THEMES_BY_ID.get(theme_id, DEFAULT_THEME)


def is_valid_theme(theme_id):
    """Return whether an ID names a user-selectable theme."""
    try:
        theme_id = int(theme_id)
    except (TypeError, ValueError):
        return False
    theme = THEMES_BY_ID.get(theme_id)
    return bool(theme and theme["configurable"])


def get_theme_identifier(theme_id, blueprint_name=None):
    """Resolve a theme ID, forcing the Basic blueprint onto Simple."""
    if blueprint_name == "basic":
        return SIMPLE_THEME_IDENTIFIER
    return get_theme(theme_id)["identifier"]


def get_theme_by_identifier(identifier):
    return THEMES_BY_IDENTIFIER.get(identifier, DEFAULT_THEME)


def template_path(identifier, template_name):
    """Build a theme template path after rejecting traversal components."""
    if not isinstance(template_name, str) or not template_name:
        raise ValueError("Theme template name must be a non-empty string")
    if "\\" in template_name or template_name.startswith("/"):
        raise ValueError("Theme template name must be relative")
    parts = template_name.split("/")
    if any(part in ("", ".", "..") for part in parts):
        raise ValueError("Theme template name contains an invalid path component")
    if identifier not in THEMES_BY_IDENTIFIER:
        raise ValueError("Unknown theme identifier")
    return f"{identifier}/templates/{template_name}"
