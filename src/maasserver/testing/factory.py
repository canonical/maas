# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test object factories."""

from __future__ import (
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = [
    "factory",
    ]

from io import BytesIO
import random
import string

from django.contrib.auth.models import User
from maasserver.models import (
    FileStorage,
    MACAddress,
    Node,
    NODE_STATUS,
    )


class Factory():

    def getRandomString(self, size=10):
        return "".join(
            random.choice(string.letters + string.digits)
            for x in xrange(size))

    def make_node(self, hostname='', set_hostname=False, status=None,
                  **kwargs):
        # hostname=None is a valid value, hence the set_hostname trick.
        if hostname is '' and set_hostname:
            hostname = self.getRandomString(255)
        if status is None:
            status = NODE_STATUS.DEFAULT_STATUS
        node = Node(hostname=hostname, status=status, **kwargs)
        node.save()
        return node

    def make_mac_address(self, address):
        """Create a MAC address."""
        node = Node()
        node.save()
        mac = MACAddress(mac_address=address, node=node)
        return mac

    def make_user(self, username=None, password=None, email=None):
        if username is None:
            username = self.getRandomString(10)
        if email is None:
            email = '%s@example.com' % self.getRandomString(10)
        if password is None:
            password = 'test'
        return User.objects.create_user(
            username=username, password=password, email=email)

    def make_admin(self, username=None, password=None, email=None):
        admin = self.make_user(
            username=username, password=password, email=email)
        admin.is_superuser = True
        admin.save()
        return admin

    def make_file_storage(self, filename=None, data=None):
        if filename is None:
            filename = self.getRandomString(255)
        if data is None:
            data = self.getRandomString(1024)

        storage = FileStorage()
        storage.save_file(filename, BytesIO(data))
        storage.save()
        return storage


# Create factory singleton.
factory = Factory()
