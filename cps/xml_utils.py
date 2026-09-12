# -*- coding: utf-8 -*-
# Calibre-Web Automated – fork of Calibre-Web
# Copyright (C) 2024-2026 Calibre-Web Automated contributors
# SPDX-License-Identifier: GPL-3.0-or-later
# See CONTRIBUTORS for full list of authors.

"""Helpers for parsing XML received from books and external services."""

from lxml import etree


def safe_xml_fromstring(data):
    """Parse XML without resolving entities or accessing the network.

    XML content handled by CWA can come from uploaded or imported books, as
    well as remote metadata providers.  Constructing a parser for each call
    avoids sharing lxml parser state between worker threads.
    """
    parser = etree.XMLParser(
        resolve_entities=False,
        no_network=True,
        load_dtd=False,
    )
    return etree.fromstring(data, parser=parser)
