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
    "calculate_digest",
    "get_shared_secret_filesystem_path",
    "get_shared_secret_from_filesystem",
]

from binascii import (
    a2b_hex,
    b2a_hex,
    )
import errno
from hashlib import sha256
from hmac import HMAC
from os import fchmod
from os.path import dirname
from sys import (
    stderr,
    stdin,
    )

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
        # Ensure that the file has sensible permissions.
        with open(secret_path, "ab") as secret_f:
            fchmod(secret_f.fileno(), 0o640)
        # Write secret to the filesystem.
        write_text_file(secret_path, secret_hex)


def calculate_digest(secret, message, salt):
    """Calculate a SHA-256 HMAC digest for the given data."""
    assert isinstance(secret, bytes)
    assert isinstance(message, bytes)
    assert isinstance(salt, bytes)
    hmacr = HMAC(secret, digestmod=sha256)
    hmacr.update(message)
    hmacr.update(salt)
    return hmacr.digest()


class InstallSharedSecretScript:
    """Install a shared-secret onto a cluster.

    This class conforms to the contract that :py:func:`MainScript.register`
    requires.
    """

    @staticmethod
    def add_arguments(parser):
        """Initialise options for storing a shared-secret.

        :param parser: An instance of :class:`ArgumentParser`.
        """

    @staticmethod
    def run(args):
        """Install a shared-secret to this cluster.

        When invoked interactively, you'll be prompted to enter the secret.
        Otherwise the secret will be read from the first line of stdin.

        In both cases, the secret must be hex/base16 encoded.
        """
        # Obtain the secret from the invoker.
        if stdin.isatty():
            try:
                secret_hex = raw_input("Secret (hex/base16 encoded): ")
            except EOFError:
                print()  # So that the shell prompt appears on the next line.
                raise SystemExit(1)
            except KeyboardInterrupt:
                print()  # So that the shell prompt appears on the next line.
                raise
        else:
            secret_hex = stdin.readline()
        # Decode and install the secret.
        try:
            secret = secret_hex.strip().decode("hex")
        except TypeError as error:
            print("Secret could not be decoded:", unicode(error), file=stderr)
            raise SystemExit(1)
        else:
            set_shared_secret_on_filesystem(secret)
            shared_secret_path = get_shared_secret_filesystem_path()
            print("Secret installed to %s." % shared_secret_path)
            raise SystemExit(0)


class CheckForSharedSecretScript:
    """Check for the presence of a shared-secret on a cluster.

    This class conforms to the contract that :py:func:`MainScript.register`
    requires.
    """

    @staticmethod
    def add_arguments(parser):
        """Initialise options for checking the presence of a shared-secret.

        :param parser: An instance of :class:`ArgumentParser`.
        """

    @staticmethod
    def run(args):
        """Check for the presence of a shared-secret on this cluster.

        Exits 0 (zero) if a shared-secret has been installed.
        """
        if get_shared_secret_from_filesystem() is None:
            print("Shared-secret is NOT installed.")
            raise SystemExit(1)
        else:
            print("Shared-secret is installed.")
            raise SystemExit(0)
