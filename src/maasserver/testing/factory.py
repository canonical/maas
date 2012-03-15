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

from django.contrib.auth.models import User
from maasserver.models import (
    ARCHITECTURE,
    FileStorage,
    MACAddress,
    Node,
    NODE_STATUS,
    )
from maasserver.testing.enum import map_enum
import maastesting.factory


class Factory(maastesting.factory.Factory):

    def getRandomEnum(self, enum):
        """Pick a random item from an enumeration class.

        :param enum: An enumeration class such as `NODE_STATUS`.
        :return: The value of one of its items.
        """
        return random.choice(list(map_enum(enum).values()))

    def getRandomChoice(self, choices):
        """Pick a random item from `choices`.

        :param choices: A sequence of choices in Django form choices format:
            [
                ('choice_id_1', "Choice name 1"),
                ('choice_id_2', "Choice name 2"),
            ]
        :return: The "id" portion of a random choice out of `choices`.
        """
        return random.choice(choices)[0]

    def make_node(self, hostname='', set_hostname=False, status=None,
                  architecture=ARCHITECTURE.i386, **kwargs):
        # hostname=None is a valid value, hence the set_hostname trick.
        if hostname is '' and set_hostname:
            hostname = self.getRandomString(255)
        if status is None:
            status = NODE_STATUS.DEFAULT_STATUS
        node = Node(
            hostname=hostname, status=status, architecture=architecture,
            **kwargs)
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
            filename = self.getRandomString(100)
        if data is None:
            data = self.getRandomString(1024).encode('ascii')

        return FileStorage.objects.save_file(filename, BytesIO(data))


# Create factory singleton.
factory = Factory()
