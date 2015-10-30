# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Respond to node changes."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

from maasserver.models import Node
from maasserver.utils.signals import connect_to_field_change
from metadataserver.models.nodekey import NodeKey


def clear_nodekey_when_owner_changes(node, old_values, deleted=False):
    """Erase related `NodeKey` when node ownership changes."""
    assert not deleted, (
        "clear_nodekey_when_owner_changes is not prepared "
        "to deal with deletion of nodes.")

    owner_id_old = old_values[0]
    owner_id_new = node.owner_id

    if owner_id_new != owner_id_old:
        NodeKey.objects.clear_token_for_node(node)


connect_to_field_change(
    clear_nodekey_when_owner_changes,
    Node, ['owner_id'], delete=False)
