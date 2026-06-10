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
import time

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


# Cache the AES-256-GCM pre-shared key, since it's expensive to derive.
# Note: this will need to change to become a dictionary if salts are supported.
_aes_psk = None
_aes_lock = Lock()

# Warning: this should not generally be changed; a MAAS server will not be able
# to communicate with any peers using this value unless it matches. This value
# should be set relatively high, in order to make a brute-force attack to
# determine the MAAS secret impractical.
DEFAULT_ITERATION_COUNT = 100000


def _get_or_create_aes_psk() -> bytes:
    """Get or create the AES-256-GCM pre-shared key.

    The key is cached globally and derived from the MAAS secret using PBKDF2.
    """
    with _aes_lock:
        global _aes_psk
        if _aes_psk is None:
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
            _aes_psk = key
        else:
            key = _aes_psk
    return key


def _get_aesgcm_context() -> AESGCM:
    """Return an AESGCM instance based on the MAAS secret."""
    key = _get_or_create_aes_psk()
    return AESGCM(key)


def encrypt_psk(message, raw=False):
    """Encrypt the specified message using AES-256-GCM.

    Returns the encrypted token as a byte string.
    Output format: nonce (12 bytes) || timestamp (8 bytes) || ciphertext || tag (16 bytes),
    all base64-encoded. The timestamp is bound to the ciphertext as AAD.
    """
    aesgcm = _get_aesgcm_context()
    if isinstance(message, str):
        message = message.encode("utf-8")
    nonce = os.urandom(12)
    ts = int(time.time()).to_bytes(8, "big")
    ciphertext = aesgcm.encrypt(nonce, message, ts)
    token = urlsafe_b64encode(nonce + ts + ciphertext)
    if raw is True:
        token = urlsafe_b64decode(token)
    return token


def _fernet_decrypt(token: bytes, ttl: int | None = None) -> bytes:
    """Decrypt a legacy Fernet token.

    This is used only for backward compatibility during rolling upgrades.
    """
    from cryptography.fernet import Fernet

    key = _get_or_create_aes_psk()
    fernet_key = urlsafe_b64encode(key)
    fernet = Fernet(fernet_key)
    return fernet.decrypt(token, ttl=ttl)


def decrypt_psk(token, ttl=None, raw=False):
    """Decrypt the specified token using AES-256-GCM.

    For backward compatibility during rolling upgrades, falls back to
    legacy Fernet decryption if AES-256-GCM fails.

    If ttl is given, raises ValueError if the token's embedded timestamp is
    older than ttl seconds or more than 60 seconds in the future.
    """
    if raw is True:
        token = urlsafe_b64encode(token)
    if isinstance(token, str):
        token = token.encode("ascii")
    # Try AES-256-GCM first (canonical format).
    try:
        return _decrypt_aesgcm(token, ttl)
    except (InvalidTag, ValueError):
        pass  # Fall through to Fernet attempt.
    # Fall back to legacy Fernet for tokens from pre-upgrade peers.
    from cryptography.fernet import InvalidToken

    try:
        return _fernet_decrypt(token, ttl=ttl)
    except InvalidToken:
        raise ValueError(
            "Token could not be decrypted with either AES-256-GCM or "
            "legacy Fernet. Check MAAS secret key."
        ) from None


def _decrypt_aesgcm(token: bytes, ttl: int | None = None) -> bytes:
    """Decrypt and validate an AES-256-GCM token."""
    aesgcm = _get_aesgcm_context()
    raw_token = urlsafe_b64decode(token)
    if len(raw_token) < 36:  # 12 (nonce) + 8 (ts) + 16 (tag) minimum
        raise ValueError("Token too short to be valid AES-256-GCM")
    nonce = raw_token[:12]
    ts_bytes = raw_token[12:20]
    ciphertext = raw_token[20:]
    ts = int.from_bytes(ts_bytes, "big")
    plaintext = aesgcm.decrypt(nonce, ciphertext, ts_bytes)
    age = time.time() - ts
    if age < -60:
        raise ValueError(
            f"Token timestamp is too far in the future (age {age:.1f}s)"
        )
    if ttl is not None and age > ttl:
        raise ValueError(f"Token has expired (age {age:.1f}s > ttl {ttl}s)")
    return plaintext


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
