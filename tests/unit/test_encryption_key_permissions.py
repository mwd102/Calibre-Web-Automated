"""Regression tests for encryption-key file permissions."""

import os
import stat

import pytest
from cryptography.fernet import Fernet

from cps.config_sql import get_encryption_key


pytestmark = pytest.mark.unit


@pytest.mark.skipif(os.name != "posix", reason="Unix file permissions only")
def test_generated_encryption_key_is_owner_only(tmp_path):
    key_path = tmp_path / ".key"
    previous_umask = os.umask(0)
    try:
        key, error = get_encryption_key(str(tmp_path))
    finally:
        os.umask(previous_umask)

    assert error == ""
    assert key == key_path.read_bytes()
    assert stat.S_IMODE(key_path.stat().st_mode) == 0o600


def test_existing_valid_encryption_key_is_preserved(tmp_path):
    key_path = tmp_path / ".key"
    existing_key = Fernet.generate_key()
    key_path.write_bytes(existing_key)
    key_path.chmod(0o640)

    key, error = get_encryption_key(str(tmp_path))

    assert error == ""
    assert key == existing_key
    assert key_path.read_bytes() == existing_key
    assert stat.S_IMODE(key_path.stat().st_mode) == 0o640
