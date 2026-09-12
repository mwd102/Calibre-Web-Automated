# -*- coding: utf-8 -*-
# Calibre-Web Automated – fork of Calibre-Web
# SPDX-License-Identifier: GPL-3.0-or-later

from pathlib import Path

from cps.jinjia import clean_string


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_clean_string_removes_script_markup_but_preserves_supported_html():
    rendered = clean_string(
        '<p>Useful <strong>description</strong></p>'
        '<script>alert("xss")</script>'
        '<img src="x" onerror="alert(1)">'
    )

    assert '<p>Useful <strong>description</strong></p>' in rendered
    assert '<script>' not in rendered
    assert '<img' not in rendered
    assert '&lt;script&gt;' in rendered
    assert '&lt;img' in rendered


def test_html_comment_sinks_use_the_sanitizer():
    for template_name in ('detail.html', 'listenmp3.html'):
        template = (REPO_ROOT / 'cps' / 'templates' / template_name).read_text(encoding='utf-8')

        assert 'entry.comments[0].text|clean_string|safe' in template
        assert 'column.value|clean_string|safe' in template
        assert 'entry.comments[0].text|safe' not in template
        assert 'column.value|safe' not in template
