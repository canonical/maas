# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test object factories."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = [
    "factory",
    ]

from io import BytesIO
import random
import time

from django.contrib.auth.models import User
from maasserver.enum import (
    ARCHITECTURE,
    NODE_STATUS,
    )
from maasserver.models import (
    FileStorage,
    MACAddress,
    Node,
    NodeGroup,
    SSHKey,
    )
from maasserver.models.node import NODE_TRANSITIONS
from maasserver.models.user import create_auth_token
from maasserver.testing import (
    get_data,
    reload_object,
    )
from maasserver.utils import map_enum
import maastesting.factory
from metadataserver.models import NodeCommissionResult

# We have a limited number of public keys:
# src/maasserver/tests/data/test_rsa{0, 1, 2, 3, 4}.pub
MAX_PUBLIC_KEYS = 5


ALL_NODE_STATES = map_enum(NODE_STATUS).values()


class Factory(maastesting.factory.Factory):

    def getRandomEnum(self, enum):
        """Pick a random item from an enumeration class.

        :param enum: An enumeration class such as `NODE_STATUS`.
        :return: The value of one of its items.
        """
        return random.choice(list(map_enum(enum).values()))

    def getRandomChoice(self, choices, but_not=None):
        """Pick a random item from `choices`.

        :param choices: A sequence of choices in Django form choices format:
            [
                ('choice_id_1', "Choice name 1"),
                ('choice_id_2', "Choice name 2"),
            ]
        :param but_not: A list of choices' IDs to exclude.
        :type but_not: Sequence.
        :return: The "id" portion of a random choice out of `choices`.
        """
        if but_not is None:
            but_not = ()
        return random.choice(
            [choice for choice in choices if choice[0] not in but_not])[0]

    def _save_node_unchecked(self, node):
        """Save a :class:`Node`, but circumvent status transition checks."""
        valid_initial_states = NODE_TRANSITIONS[None]
        NODE_TRANSITIONS[None] = ALL_NODE_STATES
        try:
            node.save()
        finally:
            NODE_TRANSITIONS[None] = valid_initial_states

    def make_node(self, mac=False, hostname='', set_hostname=False,
                  status=None, architecture=ARCHITECTURE.i386, updated=None,
                  created=None, **kwargs):
        # hostname=None is a valid value, hence the set_hostname trick.
        if hostname is '' and set_hostname:
            hostname = self.getRandomString(255)
        if status is None:
            status = NODE_STATUS.DEFAULT_STATUS
        node = Node(
            hostname=hostname, status=status, architecture=architecture,
            **kwargs)
        self._save_node_unchecked(node)
        if mac:
            self.make_mac_address(node=node)

        # Update the 'updated'/'created' fields with a call to 'update'
        # preventing a call to save() from overriding the values.
        if updated is not None:
            Node.objects.filter(id=node.id).update(updated=updated)
        if created is not None:
            Node.objects.filter(id=node.id).update(created=created)
        return reload_object(node)

    def make_node_group(self, api_token=None, worker_ip=None,
                        subnet_mask=None, broadcast_ip=None, router_ip=None,
                        ip_range_low=None, ip_range_high=None, **kwargs):
        if api_token is None:
            user = self.make_user()
            api_token = create_auth_token(user)
        if worker_ip is None:
            worker_ip = factory.getRandomIPAddress()
        if subnet_mask is None:
            subnet_mask = factory.getRandomIPAddress()
        if broadcast_ip is None:
            broadcast_ip = factory.getRandomIPAddress()
        if router_ip is None:
            router_ip = factory.getRandomIPAddress()
        if ip_range_low is None:
            ip_range_low = factory.getRandomIPAddress()
        if ip_range_high is None:
            ip_range_high = factory.getRandomIPAddress()
        ng = NodeGroup(
            api_token=api_token, api_key=api_token.key, worker_ip=worker_ip,
            subnet_mask=subnet_mask, broadcast_ip=broadcast_ip,
            router_ip=router_ip, ip_range_low=ip_range_low,
            ip_range_high=ip_range_high, **kwargs)
        ng.save()
        return ng

    def make_node_commission_result(self, node=None, name=None, data=None):
        if node is None:
            node = self.make_node()
        if name is None:
            name = "ncrname-" + self.getRandomString(92)
        if data is None:
            data = "ncrdata-" + self.getRandomString(1000)
        ncr = NodeCommissionResult(node=node, name=name, data=data)
        ncr.save()
        return ncr

    def make_mac_address(self, address=None, node=None):
        """Create a MAC address."""
        if node is None:
            node = self.make_node()
        if address is None:
            address = self.getRandomMACAddress()
        mac = MACAddress(mac_address=address, node=node)
        mac.save()
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

    def make_sshkey(self, user, key_string=None):
        if key_string is None:
            key_string = get_data('data/test_rsa0.pub')
        key = SSHKey(key=key_string, user=user)
        key.save()
        return key

    def make_user_with_keys(self, n_keys=2, user=None, **kwargs):
        """Create a user with n `SSHKey`.  If user is not None, use this user
        instead of creating one.

        Additional keyword arguments are passed to `make_user()`.
        """
        if n_keys > MAX_PUBLIC_KEYS:
            raise RuntimeError(
                "Cannot create more than %d public keys.  If you need more: "
                "add more keys in src/maasserver/tests/data/."
                % MAX_PUBLIC_KEYS)
        if user is None:
            user = self.make_user(**kwargs)
        keys = []
        for i in range(n_keys):
            key_string = get_data('data/test_rsa%d.pub' % i)
            key = SSHKey(user=user, key=key_string)
            key.save()
            keys.append(key)
        return user, keys

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

    def make_oauth_header(self, **kwargs):
        """Fake an OAuth authorization header.

        This will use arbitrary values.  Pass as keyword arguments any
        header items that you wish to override.
        """
        items = {
            'realm': self.getRandomString(),
            'oauth_nonce': random.randint(0, 99999),
            'oauth_timestamp': time.time(),
            'oauth_consumer_key': self.getRandomString(18),
            'oauth_signature_method': 'PLAINTEXT',
            'oauth_version': '1.0',
            'oauth_token': self.getRandomString(18),
            'oauth_signature': "%%26%s" % self.getRandomString(32),
        }
        items.update(kwargs)
        return "OAuth " + ", ".join([
            '%s="%s"' % (key, value) for key, value in items.items()])


# Create factory singleton.
factory = Factory()
