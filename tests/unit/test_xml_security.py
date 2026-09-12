# -*- coding: utf-8 -*-
# Calibre-Web Automated – fork of Calibre-Web
# Copyright (C) 2026 Calibre-Web Automated contributors
# SPDX-License-Identifier: GPL-3.0-or-later

"""Regression coverage for XML external entity hardening."""

import ast
from pathlib import Path

from cps.xml_utils import safe_xml_fromstring


REPO_ROOT = Path(__file__).resolve().parents[2]
XML_ENTRYPOINTS = (
    "cps/epub.py",
    "cps/epub_helper.py",
    "cps/fb2.py",
    "cps/readingservices.py",
    "cps/metadata_provider/dnb.py",
    "cps/web.py",
)


def test_safe_xml_parser_does_not_resolve_external_file_entity(tmp_path):
    secret = tmp_path / "secret.txt"
    secret.write_text("should not be exposed", encoding="utf-8")
    payload = (
        f'<!DOCTYPE root [<!ENTITY xxe SYSTEM "{secret.as_uri()}">]>'
        "<root>&xxe;</root>"
    ).encode("utf-8")

    root = safe_xml_fromstring(payload)

    assert root.tag == "root"
    assert "should not be exposed" not in "".join(root.itertext())


def test_xml_entrypoints_use_the_shared_safe_parser():
    for relative_path in XML_ENTRYPOINTS:
        source = (REPO_ROOT / relative_path).read_text(encoding="utf-8")
        tree = ast.parse(source)

        assert "safe_xml_fromstring" in source, relative_path
        unsafe_calls = [
            node for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "etree"
            and node.func.attr in {"fromstring", "XML", "parse", "iterparse"}
        ]
        assert not unsafe_calls, f"unsafe XML parse in {relative_path}"
