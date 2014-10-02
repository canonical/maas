# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""RPC helpers relating to clusters (a.k.a. node groups)."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    "get_cluster_status",
]

from maasserver.models.nodegroup import NodeGroup
from maasserver.utils.async import transactional
from provisioningserver.rpc.exceptions import NoSuchCluster
from provisioningserver.utils.twisted import synchronous


@synchronous
@transactional
def get_cluster_status(uuid):
    """Return the status of the given cluster.

    Return it as a structure suitable for returning in the response for
    :py:class:`~provisioningserver.rpc.region.GetClusterStatus`.
    """
    try:
        nodegroup = NodeGroup.objects.get_by_natural_key(uuid)
    except NodeGroup.DoesNotExist:
        raise NoSuchCluster.from_uuid(uuid)
    else:
        return {b"status": nodegroup.status}
