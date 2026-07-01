# Copyright 2014-2017 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from base64 import urlsafe_b64decode, urlsafe_b64encode
import binascii
from binascii import a2b_hex, b2a_hex
from hashlib import sha256
from hmac import HMAC
import os
from sys import stderr, stdin
from threading import Lock

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
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


# Warning: this should not generally be changed; a MAAS server will not be able
# to communicate with any peers using this value unless it matches. This value
# should be set relatively high, in order to make a brute-force attack to
# determine the MAAS secret impractical.
DEFAULT_ITERATION_COUNT = 100000


# Cache the AES-GCM key, since it's expensive to derive.
_aesgcm_key = None
_aesgcm_lock = Lock()


def _get_aesgcm_key() -> bytes:
    """Derive a 256-bit AES-GCM key from the MAAS shared secret.

    The key is cached in a global to prevent the expense of recalculating it.

    Uses PBKDF2-HMAC-SHA256 with a fixed salt and iteration count.
    """
    with _aesgcm_lock:
        global _aesgcm_key
        if _aesgcm_key is None:
            secret = MAAS_SECRET.get()
            if secret is None:
                raise MissingSharedSecret("MAAS shared secret not found.")
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=b"maas-rpc-aesgcm-salt",
                iterations=DEFAULT_ITERATION_COUNT,
                backend=default_backend(),
            )
            _aesgcm_key = kdf.derive(secret)
        return _aesgcm_key


def aesgcm_encrypt(plaintext: bytes) -> bytes:
    """Encrypt plaintext using AES-256-GCM.

    Format: nonce (12 bytes) || ciphertext || tag (GCM appends tag).
    """
    key = _get_aesgcm_key()
    nonce = os.urandom(12)
    aesgcm = AESGCM(key)
    ciphertext = aesgcm.encrypt(nonce, plaintext, None)
    return nonce + ciphertext


def aesgcm_decrypt(token: bytes) -> bytes:
    """Decrypt a token produced by aesgcm_encrypt.

    :param token: nonce || ciphertext || tag
    :return: plaintext bytes
    :raises ValueError: if the token is too short or authentication fails
    """
    if len(token) < 12 + 16:
        raise ValueError("Invalid token length")
    key = _get_aesgcm_key()
    nonce = token[:12]
    ciphertext = token[12:]
    aesgcm = AESGCM(key)
    try:
        return aesgcm.decrypt(nonce, ciphertext, None)
    except InvalidTag:
        raise ValueError("Authentication failed") from None


def fernet_encrypt_psk(message, raw=False):
    """Encrypts the specified message using AES-256-GCM via the MAAS secret.

    Returns the encrypted token as a byte string.  This retains the legacy
    function name for backwards compatibility.

    :param message: The message to encrypt. Must be 'bytes' or a UTF-8 'str'.
    :param raw: if True, returns raw bytes instead of base64-encoded bytes.
    :return: the encryption token, as bytes.
    """
    if isinstance(message, str):
        message = message.encode("utf-8")
    token = aesgcm_encrypt(message)
    if raw is True:
        return token
    return urlsafe_b64encode(token)


def fernet_decrypt_psk(token, ttl=None, raw=False):
    """Decrypts the specified token using AES-256-GCM via the MAAS secret.

    The ttl parameter is ignored for backwards compatibility (AES-GCM does not
    support TTL-based expiration).

    :param token: The token to decrypt. Must be 'bytes' or an ASCII base64 str.
    :param ttl: Ignored; kept for compatibility.
    :param raw: if True, treats the token as raw bytes (not base64).
    :return: bytes
    """
    # Validate secret exists before attempting to decode or decrypt.
    _ = _get_aesgcm_key()
    if isinstance(token, str):
        token = token.encode("ascii")
    if raw is not True:
        token = urlsafe_b64decode(token)
    return aesgcm_decrypt(token)


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
