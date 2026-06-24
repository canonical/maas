#  Copyright 2026 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).
"""FIPS structured audit-logging helpers for MAAS."""

import logging

FIPS_MODE_DETECTED = "fips_mode_detected"
FIPS_MODE_UNREADABLE = "fips_mode_unreadable"
FIPS_TLS_HANDSHAKE = "fips_tls_handshake"
FIPS_SSH_AUTHENTICATION = "fips_ssh_authentication"
FIPS_CRYPTO_ERROR = "fips_crypto_error"
FIPS_DRIVER_REJECTED = "fips_driver_rejected"

_log = logging.getLogger("maas.fips")


def log_fips_tls_handshake(
    *,
    cipher_suite: str,
    protocol_version: str,
    peer: str,
    cert_issuer: str,
    verify_enabled: bool,
) -> None:
    _log.info(
        "%s",
        FIPS_TLS_HANDSHAKE,
        extra={
            "event": FIPS_TLS_HANDSHAKE,
            "cipher_suite": cipher_suite,
            "protocol_version": protocol_version,
            "peer": peer,
            "cert_issuer": cert_issuer,
            "verify_enabled": verify_enabled,
        },
    )


def log_fips_ssh_authentication(
    *,
    key_type: str,
    kex: str,
    cipher: str,
    mac: str,
    peer: str,
    result: str,
) -> None:
    _log.info(
        "%s",
        FIPS_SSH_AUTHENTICATION,
        extra={
            "event": FIPS_SSH_AUTHENTICATION,
            "key_type": key_type,
            "kex": kex,
            "cipher": cipher,
            "mac": mac,
            "peer": peer,
            "result": result,
        },
    )


def log_fips_crypto_error(
    *,
    operation: str,
    error: str,
    algorithm: str,
    peer: str = "",
) -> None:
    _log.error(
        "%s",
        FIPS_CRYPTO_ERROR,
        extra={
            "event": FIPS_CRYPTO_ERROR,
            "operation": operation,
            "error": error,
            "algorithm": algorithm,
            "peer": peer,
        },
    )


def log_fips_driver_rejected(*, driver: str, reason: str) -> None:
    _log.error(
        "%s",
        FIPS_DRIVER_REJECTED,
        extra={
            "event": FIPS_DRIVER_REJECTED,
            "driver": driver,
            "reason": reason,
        },
    )
