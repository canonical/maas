#  Copyright 2025-2026 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

import hashlib

# Security Log Type
SECURITY = "security"


def hash_token_for_logging(token: str) -> str:
    """
    Hash a token using SHA-256 for secure logging.

    Args:
        token: The token string to hash

    Returns:
        The SHA-256 hash of the token as a hexadecimal string
    """
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
AUTHN_TOKEN_CREATED = "AUTHN_token_created"
AUTHN_TOKEN_DELETED = "AUTHN_token_deleted"
AUTHN_TOKEN_REVOKED = "AUTHN_token_revoked"
AUTHN_TOKEN_REUSED = "AUTHN_token_reused"
