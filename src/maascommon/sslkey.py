# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from OpenSSL import crypto


def is_valid_ssl_key(key: str):
    """Ascertain whether the given key value contains a valid SSL key."""
    try:
        crypto.load_certificate(crypto.FILETYPE_PEM, key.encode("ascii"))
        return True
    except Exception:
        # crypto.load_certificate raises all sorts of exceptions.
        # Here, we catch them all and return a ValidationError since this
        # method only aims at validating keys and not return the exact
        # cause of the failure.
        return False
