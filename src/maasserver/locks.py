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
    "eventloop",
    "security",
    "startup",
]

from maasserver.utils.dblocks import DatabaseLock

# Lock around starting-up a MAAS region.
startup = DatabaseLock(1)

# Lock around performing critical security-related operations, like
# generating or signing certificates.
security = DatabaseLock(2)

# Lock used when starting up the event-loop.
eventloop = DatabaseLock(3)

# Lock used to only allow one instance of importing boot images to occur
# at a time.
import_images = DatabaseLock(4)
