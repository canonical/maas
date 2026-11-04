#  Copyright 2026 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).


def get_bearer_token(authorization_header: str | None) -> str | None:
    """Return the token from an `Authorization: bearer <token>` header, or None."""
    if authorization_header and authorization_header.lower().startswith(
        "bearer "
    ):
        return authorization_header.split(" ")[1]
    return None
