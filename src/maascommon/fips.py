#  Copyright 2026 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

import base64
import dataclasses
import struct
import threading

from pydantic import BaseModel
import structlog

FIPS_ENABLED_PATH = "/proc/sys/crypto/fips_enabled"

logger = structlog.getLogger()


class FIPSStatus(BaseModel):
    fips_enabled: bool
    detection_source: str = FIPS_ENABLED_PATH
    detection_error: str | None = None


@dataclasses.dataclass(frozen=True)
class FIPSSSHConfig:
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
        "ecdh-sha2-nistp521",
        "diffie-hellman-group14-sha256",
        "diffie-hellman-group16-sha512",
    )
    macs: tuple[str, ...] = (
        "hmac-sha2-256",
        "hmac-sha2-512",
        "hmac-sha2-256-etm@openssh.com",
        "hmac-sha2-512-etm@openssh.com",
    )
    key_types: tuple[str, ...] = (
        "ecdsa-sha2-nistp256",
        "ecdsa-sha2-nistp384",
        "ecdsa-sha2-nistp521",
        "rsa-sha2-256",
        "rsa-sha2-512",
    )


FIPS_SSH_CONFIG: FIPSSSHConfig = FIPSSSHConfig()


def detect_fips_mode() -> bool:
    try:
        with open(FIPS_ENABLED_PATH) as fips_enabled_file:
            return fips_enabled_file.read().strip() == "1"
    except FileNotFoundError:
        return False
    except OSError as exc:
        logger.warning(
            "Unable to detect FIPS mode",
            path=FIPS_ENABLED_PATH,
            error=str(exc),
        )
        return False


_fips_lock = threading.Lock()
_fips_checked = False
_fips_value = False


def is_fips_enabled() -> bool:
    global _fips_checked, _fips_value
    if not _fips_checked:
        with _fips_lock:
            if not _fips_checked:
                _fips_value = detect_fips_mode()
                _fips_checked = True
    return _fips_value


def get_fips_ssh_config() -> dict[str, list[str]]:
    """Return paramiko keyword arguments that restrict SSH algorithms to FIPS-approved sets.

    Returns a dict with ``ciphers``, ``kex``, ``macs``, and ``key_types`` keys
    containing the explicit allow-lists.  These are passed directly to
    ``SSHClient.connect()`` to override paramiko's defaults rather than
    computing a disabled set from paramiko internals.
    """
    return {
        "ciphers": list(FIPS_SSH_CONFIG.ciphers),
        "kex": list(FIPS_SSH_CONFIG.kex),
        "macs": list(FIPS_SSH_CONFIG.macs),
        "key_types": list(FIPS_SSH_CONFIG.key_types),
    }


# Note: ssh-rsa is excluded because it uses SHA-1 for signatures by default,
# which is not FIPS-approved. Only rsa-sha2-256 and rsa-sha2-512 are permitted.
FIPS_ALLOWED_SSH_KEY_TYPES: frozenset[str] = frozenset(
    {
        "ecdsa-sha2-nistp256",
        "ecdsa-sha2-nistp384",
        "ecdsa-sha2-nistp521",
        "rsa-sha2-256",
        "rsa-sha2-512",
    }
)

FIPS_DISALLOWED_SSH_KEY_TYPES: frozenset[str] = frozenset(
    {
        "ssh-dss",  # DSA – not FIPS 140-2/140-3 approved
        "ssh-ed25519",  # Curve25519 – not on NIST approved list
        "sk-ssh-ed25519@openssh.com",  # FIDO ed25519 – Curve25519 not FIPS approved
    }
)

# FIDO/security-key types that wrap FIPS-approved algorithms but whose
# hardware-resident nature prevents MAAS from verifying FIPS compliance of
# the authenticator itself.
FIPS_DISALLOWED_FIDO_KEY_TYPES: frozenset[str] = frozenset(
    {
        "sk-ecdsa-sha2-nistp256@openssh.com",
        "sk-ecdsa-sha2-nistp384@openssh.com",
        "sk-ecdsa-sha2-nistp521@openssh.com",
    }
)

FIPS_SSH_ALLOWED_ALTERNATIVES: list[str] = [
    "ECDSA with NIST P-256/384/521 (ecdsa-sha2-nistp256/384/521)",
    "RSA ≥ 2048 bits (rsa-sha2-256/512)",
]

_RSA_KEY_TYPES: frozenset[str] = frozenset(
    {"rsa-sha2-256", "rsa-sha2-512"}
)


def _parse_rsa_key_bits(blob_b64: str) -> int | None:
    """Return the RSA modulus bit length from a base64-encoded SSH public key blob.

    Returns None if the blob cannot be parsed.
    """
    try:
        data = base64.b64decode(blob_b64)
        offset = 0

        # Skip algorithm name field
        (name_len,) = struct.unpack_from(">I", data, offset)
        offset += 4 + name_len

        # Skip public exponent field
        (exp_len,) = struct.unpack_from(">I", data, offset)
        offset += 4 + exp_len

        # Read modulus field
        (mod_len,) = struct.unpack_from(">I", data, offset)
        offset += 4
        modulus_bytes = data[offset : offset + mod_len]

        return int.from_bytes(modulus_bytes, "big").bit_length()
    except Exception:  # noqa: BLE001
        return None


def validate_ssh_key_fips_compliance(
    key_str: str,
) -> tuple[bool, str | None, list[str]]:
    """Validate an SSH public key against FIPS 140-2/140-3 restrictions.

    Returns (is_valid, rejection_reason, allowed_alternatives).
    """
    parts = key_str.strip().split()
    if not parts:
        return False, "Empty SSH key", FIPS_SSH_ALLOWED_ALTERNATIVES

    key_type = parts[0]

    if key_type in FIPS_DISALLOWED_SSH_KEY_TYPES:
        return (
            False,
            (
                f"SSH key type '{key_type}' is not permitted in FIPS mode. "
                "DSA (ssh-dss) and Curve25519 (ssh-ed25519) keys are not "
                "FIPS 140-2/140-3 approved."
            ),
            FIPS_SSH_ALLOWED_ALTERNATIVES,
        )

    if key_type in FIPS_DISALLOWED_FIDO_KEY_TYPES:
        return (
            False,
            (
                f"SSH key type '{key_type}' is not permitted in FIPS mode. "
                "FIDO/security-key types cannot be verified for FIPS "
                "compliance by MAAS. Use a plain ECDSA or RSA key."
            ),
            FIPS_SSH_ALLOWED_ALTERNATIVES,
        )

    if key_type not in FIPS_ALLOWED_SSH_KEY_TYPES:
        # Unknown / unrecognised key type – reject conservatively.
        return (
            False,
            (
                f"SSH key type '{key_type}' is not recognised as a "
                "FIPS-approved algorithm."
            ),
            FIPS_SSH_ALLOWED_ALTERNATIVES,
        )

    # For RSA key types that passed the algorithm check, validate key size.
    if key_type in _RSA_KEY_TYPES and len(parts) >= 2:
        bits = _parse_rsa_key_bits(parts[1])
        if bits is not None and bits < 2048:
            return (
                False,
                (
                    f"RSA key size {bits} bits is below the FIPS minimum of "
                    "2048 bits."
                ),
                FIPS_SSH_ALLOWED_ALTERNATIVES,
            )

    return True, None, []


FIPS_CERT_ALLOWED_ALTERNATIVES: list[str] = [
    "RSA ≥ 2048 bits with SHA-256 or stronger signature hash",
    "ECDSA P-256/384/521 with SHA-256 or stronger signature hash",
]


def validate_ssl_cert_fips_compliance(
    cert_pem: str,
) -> tuple[bool, str | None, list[str]]:
    """Validate a PEM X.509 certificate against FIPS 140-2/140-3 restrictions.

    Returns (is_valid, rejection_reason, allowed_alternatives).
    """
    try:
        from cryptography import x509 as _x509
        from cryptography.hazmat.primitives import hashes as _hashes
        from cryptography.hazmat.primitives.asymmetric import dsa as _dsa
        from cryptography.hazmat.primitives.asymmetric import rsa as _rsa

        cert = _x509.load_pem_x509_certificate(cert_pem.strip().encode())
    except Exception:  # noqa: BLE001
        return False, "Unable to parse PEM certificate for FIPS validation", FIPS_CERT_ALLOWED_ALTERNATIVES

    sig_hash = cert.signature_hash_algorithm
    if sig_hash is not None:
        disallowed_hashes = (_hashes.MD5, _hashes.SHA1)
        if isinstance(sig_hash, disallowed_hashes):
            return (
                False,
                (
                    f"Certificate signature uses {sig_hash.name!r} which is "
                    "not permitted in FIPS mode. Use SHA-256 or stronger."
                ),
                FIPS_CERT_ALLOWED_ALTERNATIVES,
            )

    pub_key = cert.public_key()
    if isinstance(pub_key, _dsa.DSAPublicKey):
        return (
            False,
            "DSA public keys are not FIPS 140-3 approved.",
            FIPS_CERT_ALLOWED_ALTERNATIVES,
        )
    if isinstance(pub_key, _rsa.RSAPublicKey) and pub_key.key_size < 2048:
        return (
            False,
            (
                f"RSA key size {pub_key.key_size} bits is below the "
                "FIPS minimum of 2048 bits."
            ),
            FIPS_CERT_ALLOWED_ALTERNATIVES,
        )

    return True, None, []
