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
    cert_valid: bool,
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
            "cert_valid": cert_valid,
        },
    )


def log_fips_tls_handshake_from_sslobj(ssl_object, peer: str) -> None:
    """Emit a ``fips_tls_handshake`` audit event from a stdlib SSL object.

    ``ssl_object`` is an :class:`ssl.SSLSocket`/:class:`ssl.SSLObject` as
    exposed by aiohttp/httpx transports via ``get_extra_info("ssl_object")``.
    No-op on non-FIPS hosts or when ``ssl_object`` is ``None`` (plain HTTP).
    """
    from maascommon.fips import is_fips_enabled

    if ssl_object is None or not is_fips_enabled():
        return

    cipher = ssl_object.cipher()
    peer_cert = ssl_object.getpeercert()
    cert_issuer = "unknown"
    if peer_cert:
        issuer = dict(item[0] for item in peer_cert.get("issuer", ()))
        cert_issuer = issuer.get("commonName", "unknown")
    log_fips_tls_handshake(
        cipher_suite=cipher[0] if cipher else "unknown",
        protocol_version=ssl_object.version() or "unknown",
        peer=peer,
        cert_issuer=cert_issuer,
        cert_valid=bool(peer_cert),
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
