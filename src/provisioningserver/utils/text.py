# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Text-processing utilities."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    'normalise_whitespace',
    ]


def normalise_whitespace(text):
    """Replace any whitespace sequence in `text` with just a single space."""
    return ' '.join(text.split())
