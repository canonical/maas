#  Copyright 2026 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).
"""FIPS mode detection and SSH algorithm allow-lists for MAAS."""

import base64
from functools import lru_cache
import logging
from pathlib import Path
import struct
from typing import NamedTuple

from cryptography import x509
from cryptography.hazmat.primitives.asymmetric.dsa import DSAPublicKey
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPublicKey
from cryptography.x509.oid import SignatureAlgorithmOID

from maascommon.logging.security import (
    FIPS_MODE_DETECTED,
    FIPS_MODE_UNREADABLE,
)

FIPS_PROC_PATH = Path("/proc/sys/crypto/fips_enabled")


class FIPSStatus(NamedTuple):
    """Cached result of host FIPS mode detection."""

    enabled: bool
    detection_error: str | None = None


@lru_cache(maxsize=1)
def get_fips_status() -> FIPSStatus:
    """Detect FIPS mode from the kernel procfs entry.

    Reads ``/proc/sys/crypto/fips_enabled`` once and caches the result for
    the process lifetime.  Returns a non-FIPS status when the file is absent
    (standard non-FIPS host) or unreadable (logs WARNING and defaults safe).
    """
    log = logging.getLogger("maas.fips")
    try:
        if not FIPS_PROC_PATH.exists():
            log.info("%s fips_mode=%s", FIPS_MODE_DETECTED, False)
            return FIPSStatus(enabled=False)
        content = FIPS_PROC_PATH.read_text().strip()
        enabled = content == "1"
        log.info("%s fips_mode=%s", FIPS_MODE_DETECTED, enabled)
        return FIPSStatus(enabled=enabled)
    except OSError as e:
        log.warning(
            "%s fips_mode=%s detection_error=%s",
            FIPS_MODE_UNREADABLE,
            False,
            str(e),
        )
        return FIPSStatus(enabled=False, detection_error=str(e))


def is_fips_enabled() -> bool:
    """Return True when the host kernel has FIPS mode enabled."""
    return get_fips_status().enabled


class FIPSSSHConfig(NamedTuple):
    """FIPS-approved SSH algorithm allow-lists for paramiko connections.

    These are *transport-layer* algorithm identifiers used by paramiko when
    negotiating an SSH session.  They differ from the stored SSH public-key
    type strings accepted at the API boundary (see ``validate_fips_ssh_public_key``):
    for example, RSA keys are stored as ``ssh-rsa`` but advertised on the wire
    as ``rsa-sha2-256`` / ``rsa-sha2-512``.
    """

    ciphers: tuple[str, ...] = (
        "aes128-ctr",
        "aes192-ctr",
        "aes256-ctr",
        "aes128-gcm@openssh.com",
        "aes256-gcm@openssh.com",
    )
    kex: tuple[str, ...] = (
        "ecdh-sha2-nistp256",
        "ecdh-sha2-nistp384",
        "diffie-hellman-group14-sha256",
    )
    macs: tuple[str, ...] = ("hmac-sha2-256", "hmac-sha2-512")
    key_types: tuple[str, ...] = (
        "ecdsa-sha2-nistp256",
        "rsa-sha2-256",
        "rsa-sha2-512",
    )


#: Singleton FIPS SSH algorithm allow-lists; import and use directly.
FIPS_SSH_CONFIG = FIPSSSHConfig()

FIPS_RSA_MIN_BITS = 2048


def rsa_ssh_key_bits(b64_body: str) -> int | None:
    """Return the RSA modulus size in bits from a base64 SSH key body.

    Parses the SSH wire format (RFC 4253 §6.6): each field is a 4-byte
    big-endian length followed by the field bytes. For ssh-rsa the fields are
    key-type, public exponent, modulus. Returns None on any parse error;
    :func:`validate_fips_ssh_public_key` treats that as fail-closed and
    rejects the key rather than assume it is compliant.
    """
    try:
        data = base64.b64decode(b64_body)
        pos = 0
        field = b""
        for _ in range(3):
            (length,) = struct.unpack_from(">I", data, pos)
            pos += 4
            field = data[pos : pos + length]
            pos += length
        modulus = field.lstrip(b"\x00") or field
        return len(modulus) * 8
    except Exception:
        return None


#: Explicit allowlist of FIPS-approved OpenSSH public-key types.
#: Any type not in this set is rejected; this is an allowlist, not a denylist.
FIPS_SSH_ALLOWED_KEY_TYPES: frozenset[str] = frozenset(
    {
        "ecdsa-sha2-nistp256",
        "ecdsa-sha2-nistp384",
        "ecdsa-sha2-nistp521",
        "ssh-rsa",
    }
)

#: Human-readable form used in violation messages across v2 and v3.
FIPS_SSH_KEY_TYPES_DESC = (
    "ecdsa-sha2-nistp256, ecdsa-sha2-nistp384, "
    "ecdsa-sha2-nistp521, ssh-rsa (>= 2048-bit)"
)


def validate_fips_ssh_public_key(normalized_key: str) -> str | None:
    """Return a FIPS-violation message for an OpenSSH public key, else None.

    Shared by the v2 and v3 SSH-key endpoints. Does NOT check whether FIPS is
    active — the caller gates on :func:`is_fips_enabled`. ``normalized_key`` is
    an OpenSSH-format key: ``"<type> <base64> [comment]"``.

    Uses an allowlist: any key type not in :data:`FIPS_SSH_ALLOWED_KEY_TYPES`
    is rejected so that future weak algorithms fail closed rather than passing
    through silently.
    """
    parts = normalized_key.split()
    if not parts:
        return None
    key_type = parts[0]
    if key_type not in FIPS_SSH_ALLOWED_KEY_TYPES:
        return (
            f"Key type {key_type!r} is not FIPS-compliant. "
            f"Allowed: {FIPS_SSH_KEY_TYPES_DESC}"
        )
    if key_type == "ssh-rsa" and len(parts) >= 2:
        bits = rsa_ssh_key_bits(parts[1])
        if bits is None:
            return (
                "RSA key size could not be determined from its base64 "
                "body; the key is rejected rather than assumed compliant"
            )
        if bits < FIPS_RSA_MIN_BITS:
            return (
                f"RSA key size {bits} bits is below the FIPS minimum "
                f"of {FIPS_RSA_MIN_BITS}"
            )
    return None


# `ObjectIdentifier` has no public human-readable name accessor (`._name`
# is private); spell these out explicitly instead.
_WEAK_TLS_SIGNATURE_ALGORITHM_NAMES = {
    SignatureAlgorithmOID.RSA_WITH_SHA1: "RSA-SHA1",
    SignatureAlgorithmOID.ECDSA_WITH_SHA1: "ECDSA-SHA1",
    SignatureAlgorithmOID.DSA_WITH_SHA1: "DSA-SHA1",
    SignatureAlgorithmOID.RSA_WITH_MD5: "RSA-MD5",
}


def validate_fips_tls_certificate(cert: x509.Certificate) -> str | None:
    """Return a FIPS-violation message for an x509 certificate, else None.

    Rejects SHA-1/MD5-signed certificates, DSA keys, and RSA keys below
    :data:`FIPS_RSA_MIN_BITS`. Shared by every caller that validates a
    TLS/SSL certificate under FIPS mode (hardening's API TLS cert,
    user-uploaded SSL keys in both the v3 service layer and the legacy
    Django model), so the compliance rule lives in exactly one place.

    Does NOT check whether FIPS is active -- the caller gates on
    :func:`is_fips_enabled`.
    """
    weak_signature_algorithm = _WEAK_TLS_SIGNATURE_ALGORITHM_NAMES.get(
        cert.signature_algorithm_oid
    )
    if weak_signature_algorithm is not None:
        return (
            f"Certificate signed with {weak_signature_algorithm} is not "
            "FIPS-compliant. Use SHA-256 or stronger."
        )

    pub_key = cert.public_key()
    if isinstance(pub_key, DSAPublicKey):
        return "DSA keys are not FIPS-compliant."
    if (
        isinstance(pub_key, RSAPublicKey)
        and pub_key.key_size < FIPS_RSA_MIN_BITS
    ):
        return (
            f"RSA key size {pub_key.key_size} bits is below the FIPS "
            f"minimum of {FIPS_RSA_MIN_BITS} bits."
        )
    return None
