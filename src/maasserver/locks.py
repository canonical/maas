# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Region-wide locks."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    "startup",
]

from maasserver.utils.dblocks import DatabaseLock

# Lock around starting-up a MAAS region.
startup = DatabaseLock(1)
