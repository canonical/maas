# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Respond to node changes."""

__all__ = [
    "signals",
]

from maasserver.models import Node
from maasserver.utils.signals import SignalsManager
from metadataserver.models.nodekey import NodeKey


signals = SignalsManager()


def clear_nodekey_when_owner_changes(node, old_values, deleted=False):
    """Erase related `NodeKey` when node ownership changes."""
    assert not deleted, (
        "clear_nodekey_when_owner_changes is not prepared "
        "to deal with deletion of nodes.")

    owner_id_old = old_values[0]
    owner_id_new = node.owner_id

    if owner_id_new != owner_id_old:
        NodeKey.objects.clear_token_for_node(node)


signals.watch_fields(
    clear_nodekey_when_owner_changes,
    Node, ['owner_id'], delete=False)


# Enable all signals by default.
signals.enable()
