# Copyright 2014-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Region-wide locks."""

__all__ = [
    "eventloop",
    "security",
    "startup",
]

from maasserver.utils.dblocks import (
    DatabaseLock,
    DatabaseXactLock,
)

# Lock around starting-up a MAAS region.
startup = DatabaseLock(1)

# Lock around performing critical security-related operations, like
# generating or signing certificates.
security = DatabaseLock(2)

# Lock used when starting up the event-loop.
eventloop = DatabaseLock(3)

# Lock around importing boot images, used exclusively.
import_images = DatabaseLock(4)

# Lock to prevent concurrent changes to DNS configuration.
dns = DatabaseLock(6)

# Lock to prevent concurrent acquisition of nodes.
node_acquire = DatabaseXactLock(7)

# Lock to prevent concurrent allocation of StaticIPAddress
staticip_acquire = DatabaseXactLock(8)
