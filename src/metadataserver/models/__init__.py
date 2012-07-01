# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Model for the metadata server.

DO NOT add new models to this module.  Add them to the package as separate
modules, but import them here and add them to `__all__`.
"""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = [
    'NodeCommissionResult',
    'NodeKey',
    'NodeUserData',
    ]

from django.db.models import (
    CharField,
    ForeignKey,
    Manager,
    Model,
    )
from django.shortcuts import get_object_or_404
from maasserver.models import Node
from maasserver.models.cleansave import CleanSave
from maasserver.models.user import create_auth_token
from maasserver.utils import ignore_unused
from metadataserver import DefaultMeta
from metadataserver.models.nodeuserdata import NodeUserData
from metadataserver.nodeinituser import get_node_init_user
from piston.models import (
    KEY_SIZE,
    Token,
    )


ignore_unused(NodeUserData)


class NodeKeyManager(Manager):
# Scheduled for model migration on 2012-07-02
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


# Scheduled for model migration on 2012-07-02
class NodeKey(CleanSave, Model):
    """Associate a Node with its OAuth (token) key.

    :ivar node: A Node.
    :ivar key: A key, to be used by `node` for logging in.  The key belongs
        to the maas-init-node user.
    """

    class Meta(DefaultMeta):
        """Needed for South to recognize this model."""

    objects = NodeKeyManager()

    node = ForeignKey(Node, null=False, editable=False, unique=True)
    token = ForeignKey(Token, null=False, editable=False, unique=True)
    key = CharField(
        max_length=KEY_SIZE, null=False, editable=False, unique=True)


class NodeCommissionResultManager(Manager):
# Scheduled for model migration on 2012-07-09
    """Utility to manage a collection of :class:`NodeCommissionResult`s."""

    def clear_results(self, node):
        """Remove all existing results for a node."""
        self.filter(node=node).delete()

    def store_data(self, node, name, data):
        """Store data about a node."""
        existing, created = self.get_or_create(
            node=node, name=name, defaults=dict(data=data))
        if not created:
            existing.data = data
            existing.save()

    def get_data(self, node, name):
        """Get data about a node."""
        ncr = get_object_or_404(NodeCommissionResult, node=node, name=name)
        return ncr.data


# Scheduled for model migration on 2012-07-09
class NodeCommissionResult(CleanSave, Model):
    """Storage for data returned from node commissioning.

    Commissioning a node results in various bits of data that need to be
    stored, such as lshw output.  This model allows storing of this data
    as unicode text, with an arbitrary name, for later retrieval.

    :ivar node: The context :class:`Node`.
    :ivar name: A unique name to use for the data being stored.
    :ivar data: The file's actual data, unicode only.
    """

    class Meta(DefaultMeta):
        unique_together = ('node', 'name')

    objects = NodeCommissionResultManager()

    node = ForeignKey(
        'maasserver.Node', null=False, editable=False, unique=False)
    name = CharField(max_length=100, unique=False, editable=False)
    data = CharField(max_length=1024 * 1024, editable=True)
