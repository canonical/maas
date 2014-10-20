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

from maasserver.utils.dblocks import DatabaseXactLock

# Lock around starting-up a MAAS region.
startup = DatabaseXactLock(1)

# Lock around performing critical security-related operations, like
# generating or signing certificates.
security = DatabaseXactLock(2)

# Lock used when starting up the event-loop.
eventloop = DatabaseXactLock(3)

# Lock used to only allow one instance of importing boot images to occur
# at a time.
import_images = DatabaseXactLock(4)

# Lock used to only allow one instance of caching boot source
# image information.
cache_sources = DatabaseXactLock(5)

# Lock to prevent concurrent changes to DNS configuration.
dns = DatabaseXactLock(6)

# Lock to prevent concurrent acquisition of nodes.
node_acquire = DatabaseXactLock(7)
