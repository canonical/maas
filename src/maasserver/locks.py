# Copyright 2014-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Region-wide locks."""

__all__ = [
    "address_allocation",
    "dns",
    "eventloop",
    "import_images",
    "node_acquire",
    "security",
    "startup",
]

from maasserver.utils.dblocks import DatabaseLock, DatabaseXactLock

# Lock around starting-up a MAAS region and connection of rack controllers.
# This can be a problem where a region controller and a rack controller try
# to create there node objects at the same time. Rack registration also
# involves populating fabrics, VLANs, and other information that may overlap
# between rack controller.
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

# Lock to help with concurrent allocation of IP addresses.
address_allocation = DatabaseLock(8)

# Lock used to be used just for rack registration. Because of lp:1705594 this
# was consolidated into the startup lock with the region controller.
# DO NOT USE '9' AGAIN, it is reserved so it doesn't break upgrades.
# rack_registration = DatabaseLock(9)

# Lock to prevent concurrent network scanning.
try_active_discovery = DatabaseLock(10).TRY

# Lock to sync information to RBAC.
rbac_sync = DatabaseLock(11)
