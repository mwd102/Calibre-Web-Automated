"""Compatibility import for application modules.

The standalone service scripts can use the same resolver without importing the
Flask application package during their lightweight startup path.
"""

from binary_helper import (  # noqa: F401
    SUPPORTED_KEPUBIFY_BINARIES,
    SUPPORTED_UNRAR_BINARIES,
    resolve_binary_path,
)
