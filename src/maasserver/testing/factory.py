# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from __future__ import (
    print_function,
    unicode_literals,
    )

"""Test object factories."""

__metaclass__ = type
__all__ = [
    "factory",
    ]

import random
import string

from maasserver.models import (
    MACAddress,
    Node,
    )


class Factory():

    def getRandomString(self, size):
        return "".join(
            random.choice(string.letters + string.digits)
            for x in xrange(size))

    def make_node(self, hostname='', set_hostname=False, status=None,
                  **kwargs):
        # hostname=None is a valid value, hence the set_hostname trick.
        if hostname is '' and set_hostname:
            hostname = self.getRandomString(255)
        if status is None:
            status = u'NEW'
        node = Node(hostname=hostname, status=status, **kwargs)
        node.save()
        return node

    def make_mac_address(self, address):
        """Create a MAC address."""
        node = Node()
        node.save()
        mac = MACAddress(mac_address=address, node=node)
        return mac


# Create factory singleton.
factory = Factory()
