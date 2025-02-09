# Copyright 2012-2020 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

""":class:`NodeKey` model."""

from django.db.models import CASCADE, Manager, Model, OneToOneField
from piston3.models import Token

from maasserver.models.cleansave import CleanSave
from maasserver.models.user import create_auth_token
from maasserver.utils.orm import get_one
from metadataserver.nodeinituser import get_node_init_user


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
        :rtype: piston3.models.Token
        """
        token = create_auth_token(get_node_init_user())
        self.create(node=node, token=token)
        return token

    def get_token_for_node(self, node):
        """Find node's OAuth token, or if it doesn't have one, create it.

        This implicitly grants cloud-init (running on the node) access to the
        metadata service.

        :param node: The node that needs an oauth token for access to the
            metadata service.
        :type node: Node
        :return: An OAuth token, belonging to the node-init user, but
            uniquely associated with this node.
        :rtype: piston3.models.Token
        """
        nodekey = get_one(
            self.filter(node=node).prefetch_related("token__consumer")
        )
        if nodekey is None:
            return self._create_token(node)
        else:
            return nodekey.token

    def clear_token_for_node(self, node):
        """Find node's OAuth token; if there is one, delete it.

        :param node: The node that needs an oauth token for access to the
            metadata service.
        :type node: Node
        """
        nodekey = get_one(self.filter(node=node))
        if nodekey is not None:
            # Django emulates ON DELETE CASCADE by default which is about as
            # sensible as eating live wasps. It means that deleting the token
            # will delete `nodekey` implicitly.
            nodekey.token.delete()

    def get_node_for_key(self, key):
        """Find the Node that `key` was created for.

        :param key: The key part of a node's OAuth token.
        :type key: unicode
        :raise NodeKey.DoesNotExist: if `key` is not associated with any
            node.
        """
        return self.get(token__key=key).node


class NodeKey(CleanSave, Model):
    """Associate a Node with its OAuth (token) key.

    :ivar node: A Node.
    :ivar key: A key, to be used by `node` for logging in.  The key belongs
        to the maas-init-node user.
    """

    objects = NodeKeyManager()

    node = OneToOneField(
        "maasserver.Node", null=False, editable=False, on_delete=CASCADE
    )
    token = OneToOneField(Token, null=False, editable=False, on_delete=CASCADE)
