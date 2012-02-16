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
        :return: Consumer and Token for the node to use, attached to the
            maas-init-node user.  If passed the token's key,
            `get_node_for_key` will return `node`.
        :rtype tuple:
        """
        consumer, token = create_auth_token(get_node_init_user())
        self.create(node=node, key=token.key)
        return consumer, token

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
