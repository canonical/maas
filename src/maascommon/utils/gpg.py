#  Copyright 2026 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

"""Structural validation of ASCII-armored OpenPGP public keys."""

import base64
import re

ARMOR_HEADER = "-----BEGIN PGP PUBLIC KEY BLOCK-----"
ARMOR_FOOTER = "-----END PGP PUBLIC KEY BLOCK-----"

_ARMOR_HEADER_LINE = re.compile(r"^[A-Za-z0-9-]+: .*$")
_PUBLIC_KEY_PACKET_TAG = 6

_CRC24_INIT = 0xB704CE
_CRC24_POLY = 0x1864CFB


def _crc24(data: bytes) -> int:
    crc = _CRC24_INIT
    for byte in data:
        crc ^= byte << 16
        for _ in range(8):
            crc <<= 1
            if crc & 0x1000000:
                crc ^= _CRC24_POLY
    return crc & 0xFFFFFF


def _first_packet_tag(data: bytes) -> int | None:
    if not data or not data[0] & 0x80:
        return None
    if data[0] & 0x40:
        return data[0] & 0x3F
    return (data[0] >> 2) & 0x0F


def validate_gpg_public_key(key: str) -> None:
    """Raise `ValueError` if `key` is not an ASCII-armored public key.

    The check is purely structural (armor, base64, CRC-24 checksum and
    leading public key packet), so it works without network access.
    """
    lines = [line.strip() for line in key.strip().splitlines()]
    if len(lines) < 3 or lines[0] != ARMOR_HEADER:
        raise ValueError(
            f"Key must be an ASCII-armored PGP public key starting with "
            f"'{ARMOR_HEADER}'."
        )
    if lines[-1] != ARMOR_FOOTER:
        raise ValueError(f"Key must end with '{ARMOR_FOOTER}'.")

    body = lines[1:-1]
    while body and _ARMOR_HEADER_LINE.match(body[0]):
        body = body[1:]
    body = [line for line in body if line]

    checksum = None
    if body and body[-1].startswith("="):
        checksum = body.pop()[1:]

    try:
        data = base64.b64decode("".join(body), validate=True)
    except ValueError:
        raise ValueError("Key contains invalid base64 data.") from None
    if not data:
        raise ValueError("Key contains no data.")

    if checksum is not None:
        try:
            expected = int.from_bytes(
                base64.b64decode(checksum, validate=True), "big"
            )
        except ValueError:
            raise ValueError("Key has an invalid checksum.") from None
        if _crc24(data) != expected:
            raise ValueError("Key checksum does not match its content.")

    if _first_packet_tag(data) != _PUBLIC_KEY_PACKET_TAG:
        raise ValueError("Key does not contain a PGP public key.")
