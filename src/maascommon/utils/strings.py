# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

import secrets
import string

ALPHABET = string.ascii_letters + string.digits


def get_random_string(length: int, allowed_chars: str = ALPHABET):
    return "".join(secrets.choice(allowed_chars) for _ in range(length))
