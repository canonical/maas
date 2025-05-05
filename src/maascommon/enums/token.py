# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from enum import IntEnum


class TokenType(IntEnum):
    # Taken from https://github.com/userzimmermann/django-piston3/blob/fe1ea644bcb07332670aeceddbf0ded29bdf785a/piston/models.py#L98
    REQUEST = 1
    ACCESS = 2
