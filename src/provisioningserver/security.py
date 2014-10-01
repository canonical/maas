# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Cluster security code."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    "get_shared_secret_filesystem_path",
    "get_shared_secret_from_filesystem",
]

from binascii import (
    a2b_hex,
    b2a_hex,
    )
import errno
from os.path import dirname

from lockfile import FileLock
from provisioningserver.path import get_path
from provisioningserver.utils.fs import (
    ensure_dir,
    read_text_file,
    write_text_file,
    )


def to_hex(b):
    """Convert byte string to hex encoding."""
    assert isinstance(b, bytes)
    return b2a_hex(b).decode("ascii")


def to_bin(u):
    """Convert ASCII-only unicode string to hex encoding."""
    assert isinstance(u, unicode)
    # Strip ASCII whitespace from u before converting.
    return a2b_hex(u.encode("ascii").strip())


def get_shared_secret_filesystem_path():
    """Return the path to shared-secret on the filesystem."""
    return get_path("var", "lib", "maas", "secret")


def get_shared_secret_from_filesystem():
    """Load the secret from the filesystem.

    `get_shared_secret_filesystem_path` defines where the file will be
    written. If the directory does not already exist, this will attempt to
    create it, including all parent directories.

    :returns: A byte string of arbitrary length.
    """
    secret_path = get_shared_secret_filesystem_path()
    ensure_dir(dirname(secret_path))
    with FileLock(secret_path):
        # Load secret from the filesystem, if it exists.
        try:
            secret_hex = read_text_file(secret_path)
        except IOError as e:
            if e.errno == errno.ENOENT:
                return None
            else:
                raise
        else:
            return to_bin(secret_hex)


def set_shared_secret_on_filesystem(secret):
    """Write the secret to the filesystem.

    `get_shared_secret_filesystem_path` defines where the file will be
    written. If the directory does not already exist, this will attempt to
    create it, including all parent directories.

    :type secret: A byte string of arbitrary length.
    """
    secret_path = get_shared_secret_filesystem_path()
    ensure_dir(dirname(secret_path))
    secret_hex = to_hex(secret)
    with FileLock(secret_path):
        # Write secret to the filesystem.
        write_text_file(secret_path, secret_hex)
