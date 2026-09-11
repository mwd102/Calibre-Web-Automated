# -*- coding: utf-8 -*-
# Calibre-Web Automated – fork of Calibre-Web
# Copyright (C) 2018-2026 Calibre-Web contributors
# Copyright (C) 2024-2026 Calibre-Web Automated contributors
# SPDX-License-Identifier: GPL-3.0-or-later
# See CONTRIBUTORS for full list of authors.

"""Resolve configured optional helper binaries without accepting commands."""

import os
import sys


if sys.platform == "win32":
    SUPPORTED_UNRAR_BINARIES = ("unRAR.exe", "unrar.exe")
    SUPPORTED_KEPUBIFY_BINARIES = ("kepubify-windows-64Bit.exe",)
else:
    SUPPORTED_UNRAR_BINARIES = ("unrar", "unrar-free", "unrar-nonfree")
    SUPPORTED_KEPUBIFY_BINARIES = (
        "kepubify-linux-64bit",
        "kepubify-linux-32bit",
        "kepubify",
    )


def resolve_binary_path(configured_path, binary_names):
    """Return an allowed executable from a configured file or directory.

    A configured file is accepted only when its basename is in ``binary_names``.
    A configured directory is searched only for those exact names. Empty values
    deliberately resolve to an empty string so an administrator can disable an
    optional helper.
    """
    if not configured_path:
        return ""

    allowed_names = {binary_name.lower() for binary_name in binary_names}
    if os.path.isfile(configured_path) and os.access(configured_path, os.X_OK):
        if os.path.basename(os.path.realpath(configured_path)).lower() in allowed_names:
            return configured_path
        return ""

    if os.path.isdir(configured_path):
        for binary_name in binary_names:
            binary_path = os.path.join(configured_path, binary_name)
            if os.path.isfile(binary_path) and os.access(binary_path, os.X_OK):
                return binary_path
    return ""
