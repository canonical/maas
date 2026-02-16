# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).


def is_ulid(value: str) -> bool:
    if len(value) != 26:
        return False
    # ULIDs are base32 encoded using Crockford's base32 alphabet
    crockford_base32 = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
    return all(c in crockford_base32 for c in value.upper())
