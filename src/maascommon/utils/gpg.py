#  Copyright 2026 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

"""Basic sanity check of ASCII-armored OpenPGP public keys."""

import base64

ARMOR_HEADER = "-----BEGIN PGP PUBLIC KEY BLOCK-----"
ARMOR_FOOTER = "-----END PGP PUBLIC KEY BLOCK-----"


def validate_gpg_public_key(key: str) -> None:
    """Raise `ValueError` if `key` doesn't look like an armored public key.

    This checks the armor lines, that a blank line follows the armor
    headers, and that the body is base64. It does not verify the checksum
    or parse the key itself.
    """
    # Headers and footers might be lost from a partial copy/paste.
    lines = [line.strip() for line in key.strip().splitlines()]
    if not lines or lines[0] != ARMOR_HEADER:
        raise ValueError(f"Key must start with '{ARMOR_HEADER}'.")
    if lines[-1] != ARMOR_FOOTER:
        raise ValueError(f"Key must end with '{ARMOR_FOOTER}'.")

    first_body_line = 1
    while ": " in lines[first_body_line]:
        first_body_line += 1
    if lines[first_body_line] != "":
        raise ValueError(
            f"Key must have a blank line after '{ARMOR_HEADER}' "
            "and any header lines."
        )

    # Skip optional "Name: value" armor headers and the "=XXXX" checksum.
    body = "".join(
        line
        for line in lines[1:-1]
        if line and ": " not in line and not line.startswith("=")
    )
    if not body:
        raise ValueError("Key is empty.")
    try:
        base64.b64decode(body, validate=True)
    except ValueError:
        raise ValueError("Key contains invalid characters.") from None
