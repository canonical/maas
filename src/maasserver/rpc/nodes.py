# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""RPC helpers relating to nodes."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    "mark_node_broken",
]


from maasserver.models import Node
from maasserver.utils.async import transactional
from provisioningserver.rpc.exceptions import NoSuchNode
from provisioningserver.utils import synchronous


@synchronous
@transactional
def mark_node_broken(system_id, error_description):
    """Mark a node as broken.

    for :py:class:`~provisioningserver.rpc.region.MarkBroken`.
    """
    try:
        node = Node.objects.get(system_id=system_id)
    except Node.DoesNotExist:
        raise NoSuchNode.from_system_id(system_id)
    node.mark_broken(error_description)
