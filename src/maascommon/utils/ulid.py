# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

import secrets
import time

# Standard ULID/Crockford Base32 alphabet
_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"


def _encode_base32(value: int, length: int) -> str:
    chars = []
    for _ in range(length):
        chars.append(_ALPHABET[value % 32])
        value //= 32
    return "".join(reversed(chars))


# TODO: not a RFC compliant ULID implementation. Switch to python3-ulid when we upgrade to Resolute.
def generate_ulid() -> str:
    # 48-bit timestamp
    timestamp_ms = int(time.time() * 1000)
    timestamp_ms &= 0xFFFFFFFFFFFF

    # 80 bits of randomness
    random_bits = secrets.randbits(80)

    return _encode_base32(timestamp_ms, 10) + _encode_base32(random_bits, 16)
