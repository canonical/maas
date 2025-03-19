# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).
from html import escape

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


def find_ssl_common_name(subject: crypto.X509Name):
    """Returns the common name for the ssl key."""
    for component in subject.get_components():
        if len(component) < 2:
            continue
        if component[0] == b"CN":
            return component[1].decode("utf-8")
    return None


def get_html_display_for_key(key: str) -> str:
    """Returns the html escaped string for the key."""
    cert = crypto.load_certificate(crypto.FILETYPE_PEM, key.encode())
    subject = cert.get_subject()
    md5 = cert.digest("MD5").decode("ascii")
    cn = find_ssl_common_name(subject)
    if cn is not None:
        key = f"{cn} {md5}"
    else:
        key = md5
    return escape(key, quote=True)
