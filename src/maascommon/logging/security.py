#  Copyright 2025-2026 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

import hashlib
import logging

# Security Log Type
SECURITY = "security"


def hash_token_for_logging(token: str) -> str:
    """
    Hash a token using SHA-256 for secure logging.

    Args:
        token: The token string to hash

    Returns:
        The SHA-256 hash of the token as a 64-character hexadecimal string,
        or an error message string if the token is invalid

    Note:
        This function is designed for logging and correlation, not
        cryptographic security. The same token always produces the
        same hash, enabling log analysis while protecting token values.

        Returns "<empty_token>" if the token is empty or only whitespace
        to avoid disrupting logging flow.
    """
    if not token or not token.strip():
        return "<empty_token>"
    return hashlib.sha256(token.encode()).hexdigest()


# Authentication
AUTHN_LOGIN_SUCCESSFUL = "AUTHN_login_successful"
AUTHN_LOGIN_UNSUCCESSFUL = "AUTHN_login_unsuccessful"
AUTHN_AUTH_FAILED = "AUTHN_authentication_failed"
AUTHN_AUTH_SUCCESSFUL = "AUTHN_authentication_successful"
AUTHN_PASSWORD_CHANGED = "AUTHN_password_changed"

# Authorization
AUTHZ_FAIL = "AUTHZ_fail"
AUTHZ_ADMIN = "AUTHZ_administrative"

# Users
USER_CREATED = "USER_created"
USER_DELETED = "USER_deleted"
USER_UPDATED = "USER_updated"
ADMIN = "Admin"
USER = "User"

# Resources
CREATED = "created"
UPDATED = "updated"
DELETED = "deleted"

# Tokens
# Notes the creation of a new JWT access or freshtoken, a Rack Controller V2 (Agent) Bootstrap token, or a MSM JWT enrollment token
AUTHN_TOKEN_CREATED = "AUTHN_token_created"
# Notes the deletion of any of the above mention tokens
AUTHN_TOKEN_DELETED = "AUTHN_token_deleted"
# Notes the revoking of any of the above mention tokens
AUTHN_TOKEN_REVOKED = "AUTHN_token_revoked"
# Notes the usage of any invalid version of the above tokens.
# This could be because the token is expired, is in the wrong format, or simply does not exist in the database.
AUTHN_TOKEN_REUSED = "AUTHN_token_reused"
ACCESS_TOKEN = "access_token"
REFRESH_TOKEN = "refresh_token"
BOOTSTRAP_TOKEN = "bootstrap_token"

# FIPS structured audit-logging helpers
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
