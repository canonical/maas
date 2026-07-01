#  Copyright 2026 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).
"""FIPS mode detection and SSH algorithm allow-lists for MAAS."""

import base64
from dataclasses import dataclass
from functools import lru_cache
import logging
from pathlib import Path
import struct

from maascommon.logging.security import (
    FIPS_MODE_DETECTED,
    FIPS_MODE_UNREADABLE,
)

FIPS_PROC_PATH = Path("/proc/sys/crypto/fips_enabled")


@dataclass(frozen=True)
class FIPSStatus:
    """Cached result of host FIPS mode detection."""

    enabled: bool
    detection_source: str
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
            log.info(
                "%s fips_mode=%s source=%s",
                FIPS_MODE_DETECTED,
                False,
                "file_missing",
            )
            return FIPSStatus(enabled=False, detection_source="file_missing")
        content = FIPS_PROC_PATH.read_text().strip()
        enabled = content == "1"
        log.info(
            "%s fips_mode=%s source=%s",
            FIPS_MODE_DETECTED,
            enabled,
            str(FIPS_PROC_PATH),
        )
        return FIPSStatus(
            enabled=enabled, detection_source=str(FIPS_PROC_PATH)
        )
    except OSError as e:
        log.warning(
            "%s fips_mode=%s detection_error=%s",
            FIPS_MODE_UNREADABLE,
            False,
            str(e),
        )
        return FIPSStatus(
            enabled=False,
            detection_source=str(FIPS_PROC_PATH),
            detection_error=str(e),
        )


def is_fips_enabled() -> bool:
    """Return True when the host kernel has FIPS mode enabled."""
    return get_fips_status().enabled


@dataclass(frozen=True)
class FIPSSSHConfig:
    """FIPS-approved SSH algorithm allow-lists for paramiko connections."""

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


#: FIPS-approved SSH public-key types accepted at the API boundary. DSA and
#: Ed25519 are excluded (the latter is not implemented by the OpenSSL 3.0.13
#: FIPS provider in core24). RSA is admitted only at >= 2048 bits.
FIPS_ALLOWED_SSH_KEY_TYPES: tuple[str, ...] = (
    "ecdsa-sha2-nistp256",
    "ecdsa-sha2-nistp384",
    "ecdsa-sha2-nistp521",
    "ssh-rsa",
)

#: Human-readable allow-list used in violation messages across v2 and v3.
FIPS_SSH_KEY_TYPES_DESC = (
    "ecdsa-sha2-nistp256, ecdsa-sha2-nistp384, "
    "ecdsa-sha2-nistp521, ssh-rsa (>= 2048-bit)"
)

FIPS_RSA_MIN_BITS = 2048


def rsa_ssh_key_bits(b64_body: str) -> int | None:
    """Return the RSA modulus size in bits from a base64 SSH key body.

    Parses the SSH wire format (RFC 4253 §6.6): each field is a 4-byte
    big-endian length followed by the field bytes. For ssh-rsa the fields are
    key-type, public exponent, modulus. Returns None on any parse error so the
    caller skips the size check rather than reject a key it cannot inspect.
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


def validate_fips_ssh_public_key(normalized_key: str) -> str | None:
    """Return a FIPS-violation message for an OpenSSH public key, else None.

    Shared by the v2 and v3 SSH-key endpoints. Does NOT check whether FIPS is
    active — the caller gates on :func:`is_fips_enabled`. ``normalized_key`` is
    an OpenSSH-format key: ``"<type> <base64> [comment]"``.
    """
    parts = normalized_key.split()
    if not parts:
        return None
    key_type = parts[0]
    if key_type in ("ssh-dss", "ssh-ed25519"):
        return (
            f"Key type {key_type} is not FIPS-compliant. "
            f"Allowed: {FIPS_SSH_KEY_TYPES_DESC}"
        )
    if key_type == "ssh-rsa" and len(parts) >= 2:
        bits = rsa_ssh_key_bits(parts[1])
        if bits is not None and bits < FIPS_RSA_MIN_BITS:
            return (
                f"RSA key size {bits} bits is below the FIPS minimum "
                f"of {FIPS_RSA_MIN_BITS}"
            )
    return None
