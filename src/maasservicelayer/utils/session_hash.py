# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

import hashlib
import hmac

_DJANGO_SECRET_KEY = "<UNUSED>"

_SESSION_AUTH_HASH_KEY_SALT = (
    "django.contrib.auth.models.AbstractBaseUser.get_session_auth_hash"
)


def get_session_auth_hash(password: str) -> str:
    """Compute the session auth hash the same way Django does.
    This is needed to maintain compatiblity with v2.
    """
    key_salt = _to_bytes(_SESSION_AUTH_HASH_KEY_SALT)
    secret = _to_bytes(_DJANGO_SECRET_KEY)
    msg = _to_bytes(password)
    key = hashlib.sha256(key_salt + secret).digest()
    return hmac.new(key, msg=msg, digestmod=hashlib.sha256).hexdigest()


def _to_bytes(value: str | bytes) -> bytes:
    return value if isinstance(value, bytes) else value.encode("utf-8")
