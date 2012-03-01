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
from piston.models import (
    KEY_SIZE,
    Token,
    )


class NodeKeyManager(Manager):
    """Utility for the collection of NodeKeys.

    Each Node that needs to access the metadata service will have its own
    OAuth token, tied to the dedicated "node-init" user.  Each node will see
    just its own meta-data when it accesses the service.

    NodeKeyManager is what connects those nodes to their respective tokens.

    There's two parts to using NodeKey and NodeKeyManager:

    1.  get_token_for_node(node) gives you a token that the node can then
        access the metadata service with.  From the "token" that this
        returns, the node will need to know token.key, token.secret, and
        token.consumer.key for its credentials.

    2.  get_node_for_key(key) takes the token.key (which will be in the
        http Authorization header of a metadata request as "oauth_token")
        and looks up the associated Node.
    """

    def _create_token(self, node):
        """Create an OAuth token for a given node.

        :param node: The system that is to be allowed access to the metadata
            service.
        :type node: Node
        :return: Token for the node to use.
        :rtype: piston.models.Token
        """
        token = create_auth_token(get_node_init_user())
        self.create(node=node, token=token, key=token.key)
        return token

    def get_token_for_node(self, node):
        """Find node's OAuth token, or if it doesn't have one, create it.

        This implicitly grants cloud-init (running on the node) access to the
        metadata service.

        Barring exceptions, this will always hold:

            get_node_for_key(get_token_for_node(node).key) == node

        :param node: The node that needs an oauth token for access to the
            metadata service.
        :type node: Node
        :return: An OAuth token, belonging to the node-init user, but
            uniquely associated with this node.
        :rtype: piston.models.Token
        """
        existing_nodekey = self.filter(node=node)
        assert len(existing_nodekey) in (0, 1), (
            "Found %d keys for node (expected at most one)."
            % len(existing_nodekey))
        if len(existing_nodekey) == 0:
            return self._create_token(node)
        else:
            [nodekey] = existing_nodekey
            return nodekey.token

    def get_node_for_key(self, key):
        """Find the Node that `key` was created for.

        Barring exceptions, this will always hold:

            get_token_for_node(get_node_for_key(key)).key == key

        :param key: The key part of a node's OAuth token.
        :type key: basestring
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

    node = ForeignKey(Node, null=False, editable=False, unique=True)
    token = ForeignKey(Token, null=False, editable=False, unique=True)
    key = CharField(
        max_length=KEY_SIZE, null=False, editable=False, unique=True)


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
            wrapped_data = Bin(data)
            self.create(node=node, data=wrapped_data)
        else:
            raise AssertionError("More than one user-data entry matches.")

    def get_user_data(self, node):
        """Retrieve user data for the given node."""
        return self.get(node=node).data

    def has_user_data(self, node):
        """Do we have user data registered for node?"""
        return self.filter(node=node).exists()


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
