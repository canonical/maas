#  Copyright 2026 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

"""SSH key generation helpers for testing."""

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.asymmetric import dsa, ec, ed25519, rsa

from maascommon.fips import is_fips_enabled
from provisioningserver.security import (
    _raise_fips_crypto_error,
    FIPSCryptoError,
)


def generate_ssh_key(key_type: str, bits: int = 4096):
    """Generate an SSH private key, enforcing FIPS constraints when active.

    In FIPS mode, DSA and Ed25519 are rejected; RSA keys must be at least 2048
    bits. Outside FIPS mode, all common key types are accepted.
    """
    key_type = key_type.lower()
    fips = is_fips_enabled()

    if key_type == "dsa":
        if fips:
            _raise_fips_crypto_error(
                operation="generate_ssh_key",
                algorithm="DSA",
                reason="DSA keys are not permitted in FIPS mode",
            )
        return dsa.generate_private_key(
            key_size=bits, backend=default_backend()
        )
    elif key_type == "rsa":
        if fips and bits < 2048:
            _raise_fips_crypto_error(
                operation="generate_ssh_key",
                algorithm="RSA",
                reason=f"RSA key size {bits} is below the FIPS minimum of 2048",
            )
        return rsa.generate_private_key(
            public_exponent=65537, key_size=bits, backend=default_backend()
        )
    elif key_type == "ecdsa":
        return ec.generate_private_key(
            ec.SECP256R1(), backend=default_backend()
        )
    elif key_type == "ed25519":
        if fips:
            _raise_fips_crypto_error(
                operation="generate_ssh_key",
                algorithm="ED25519",
                reason="ED25519 keys are not permitted in FIPS mode",
            )
        return ed25519.Ed25519PrivateKey.generate()
    else:
        raise ValueError(f"Unsupported SSH key type: {key_type!r}")


__all__ = ["FIPSCryptoError", "generate_ssh_key"]
