# Copyright 2014-2017 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from base64 import urlsafe_b64decode, urlsafe_b64encode
import binascii
from binascii import a2b_hex, b2a_hex
from hashlib import sha256
from hmac import HMAC
from sys import stderr, stdin
from threading import Lock

from cryptography.fernet import Fernet
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from provisioningserver.utils.env import MAAS_SECRET, MAAS_SHARED_SECRET


class MissingSharedSecret(RuntimeError):
    """Raised when the MAAS shared secret is missing."""


def to_hex(b: bytes) -> str:
    """Convert byte string to hex encoding."""
    assert isinstance(b, bytes), f"{b!r} is not a byte string"
    return b2a_hex(b).decode("ascii")


def to_bin(u: str) -> bytes:
    """Convert ASCII-only unicode string to hex encoding."""
    assert isinstance(u, str), f"{u!r} is not a unicode string"
    # Strip ASCII whitespace from u before converting.
    return a2b_hex(u.encode("ascii").strip())


def calculate_digest(secret, message, salt):
    """Calculate a SHA-256 HMAC digest for the given data."""
    assert isinstance(secret, bytes), f"{secret!r} is not a byte string."
    assert isinstance(message, bytes), f"{message!r} is not byte string."
    assert isinstance(salt, bytes), f"{salt!r} is not a byte string."
    hmacr = HMAC(secret, digestmod=sha256)
    hmacr.update(message)
    hmacr.update(salt)
    return hmacr.digest()


# Cache the Fernet pre-shared key, since it's expensive to derive the key.
# Note: this will need to change to become a dictionary if salts are supported.
_fernet_psk = None
_fernet_lock = Lock()

# Warning: this should not generally be changed; a MAAS server will not be able
# to communicate with any peers using this value unless it matches. This value
# should be set relatively high, in order to make a brute-force attack to
# determine the MAAS secret impractical.
DEFAULT_ITERATION_COUNT = 100000


def _get_or_create_fernet_psk() -> bytes:
    """Gets or creates a pre-shared key to be used with the Fernet algorithm.

    The pre-shared key is cached in a global to prevent the expense of
    recalculating it.

    Uses the MAAS secret (typically /var/lib/maas/secret) to derive the key.

    :return: A pre-shared key suitable for use with the Fernet class.
    """
    with _fernet_lock:
        global _fernet_psk
        if _fernet_psk is None:
            secret = MAAS_SECRET.get()
            if secret is None:
                raise MissingSharedSecret("MAAS shared secret not found.")
            # Keying material is required by PBKDF2 to be a byte string.
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                # XXX: It might be better to use the maas_id for the salt.
                # But that requires the maas_id to be known in advance by all
                # parties to the encrypted communication. The format of the
                # cached pre-shared key would also need to change.
                salt=b"",
                # XXX: an infrequently-changing variable iteration count might
                # be nice, but that would require protocol support, and
                # changing the way the PSK is cached.
                iterations=DEFAULT_ITERATION_COUNT,
                backend=default_backend(),
            )
            key = kdf.derive(secret)
            key = urlsafe_b64encode(key)
            _fernet_psk = key
        else:
            key = _fernet_psk
    return key


def _get_fernet_context() -> Fernet:
    """Returns a Fernet context based on the MAAS secret."""
    key = _get_or_create_fernet_psk()
    return Fernet(key)


def fernet_encrypt_psk(message, raw=False):
    """Encrypts the specified message using the Fernet format.

    Returns the encrypted token, as a byte string.

    Note that a Fernet token includes the current time. Users decrypting a
    the token can specify a TTL (in seconds) indicating how long the encrypted
    message should be valid. So the system clock must be correct before calling
    this function.

    :param message: The message to encrypt.
    :type message: Must be of type 'bytes' or a UTF-8 'str'.
    :param raw: if True, returns the decoded base64 bytes representing the
        Fernet token. The bytes must be converted back to base64 to be
        decrypted. (Or the 'raw' argument on the corresponding
        fernet_decrypt_psk() function can be used.)
    :return: the encryption token, as a base64-encoded byte string.
    """
    fernet = _get_fernet_context()
    if isinstance(message, str):
        message = message.encode("utf-8")
    token = fernet.encrypt(message)
    if raw is True:
        token = urlsafe_b64decode(token)
    return token


def fernet_decrypt_psk(token, ttl=None, raw=False):
    """Decrypts the specified Fernet token using the MAAS secret.

    Returns the decrypted token as a byte string; the user is responsible for
    converting it to the correct format or encoding.

    :param message: The token to decrypt.
    :type token: Must be of type 'bytes', or an ASCII base64 string.
    :param ttl: Optional amount of time (in seconds) allowed to have elapsed
        before the message is rejected upon decryption. Note that the Fernet
        library considers times up to 60 seconds into the future (beyond the
        TTL) to be valid.
    :param raw: if True, treats the string as the decoded base64 bytes of a
        Fernet token, and attempts to encode them (as expected by the Fernet
        APIs) before decrypting.
    :return: bytes
    """
    if raw is True:
        token = urlsafe_b64encode(token)
    f = _get_fernet_context()
    if isinstance(token, str):
        token = token.encode("ascii")
    return f.decrypt(token, ttl=ttl)


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
                secret_hex = input("Secret (hex/base16 encoded): ")
            except EOFError:
                print()  # So that the shell prompt appears on the next line.
                raise SystemExit(1)  # noqa: B904
            except KeyboardInterrupt:
                print()  # So that the shell prompt appears on the next line.
                raise
        else:
            secret_hex = stdin.readline()
        # Decode and install the secret.
        try:
            to_bin(secret_hex.strip())
        except binascii.Error as error:
            print("Secret could not be decoded:", str(error), file=stderr)
            raise SystemExit(1)  # noqa: B904
        else:
            MAAS_SHARED_SECRET.set(secret_hex)
            print(f"Secret installed to {MAAS_SHARED_SECRET.path}.")
            raise SystemExit(0)
