# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Model for the metadata server."""

from __future__ import (
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = [
    'NodeKey',
    'NodeUserData',
    ]

from django.db.models import (
    CharField,
    ForeignKey,
    Manager,
    Model,
    )
from maasserver.models import (
    create_auth_token,
    Node,
    )
from metadataserver.fields import (
    Bin,
    BinaryField,
    )
from metadataserver.nodeinituser import get_node_init_user
from piston.models import KEY_SIZE


class NodeKeyManager(Manager):
    """Utility for the collection of NodeKeys."""

    def create_token(self, node):
        """Create an OAuth token for a given node.

        The node will be able to use these credentials for accessing the
        metadata service.  It will see its own, custom metadata.

        :param node: The system that is to be allowed access to the metadata
            service.
        :type node: Node
        :return: Token for the node to use.  It will belong to the
            maas-init-node user.  If passed the token's key,
            `get_node_for_key` will return `node`.
        :rtype: piston.models.Token
        """
        token = create_auth_token(get_node_init_user())
        self.create(node=node, key=token.key)
        return token

    def get_node_for_key(self, key):
        """Find the Node that `key` was created for.

        :raise NodeKey.DoesNotExist: if `key` is not associated with any
            node.
        """
        return self.get(key=key).node


class NodeKey(Model):
    """Associate a Node with its OAuth (token) key.

    :ivar node: A Node.
    :ivar key: A key, to be used by `node` for logging in.  The key belongs
        to the maas-init-node user.
    """

    objects = NodeKeyManager()

    node = ForeignKey(Node, null=False, editable=False)
    key = CharField(max_length=KEY_SIZE, null=False, editable=False)


class NodeUserDataManager(Manager):
    """Utility for the collection of NodeUserData items."""

    def set_user_data(self, node, data):
        """Set user data for the given node."""
        existing_entries = self.filter(node=node)
        if len(existing_entries) == 1:
            [entry] = existing_entries
            entry.data = Bin(data)
            entry.save()
        elif len(existing_entries) == 0:
            self.create(node=node, data=Bin(data))
        else:
            raise AssertionError("More than one user-data entry matches.")

    def get_user_data(self, node):
        """Retrieve user data for the given node."""
        return self.get(node=node).data


class NodeUserData(Model):
    """User-data portion of a node's metadata.

    When cloud-init sets up a node, it retrieves specific data for that node
    from the metadata service.  One portion of that is the "user-data" binary
    blob.

    :ivar node: Node that this is for.
    :ivar data: base64-encoded data.
    """

    objects = NodeUserDataManager()

    node = ForeignKey(Node, null=False, editable=False, unique=True)
    data = BinaryField(null=False)
