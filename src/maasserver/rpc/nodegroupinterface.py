# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""RPC methods for NodeGroupInterface"""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    "update_foreign_dhcp_ip",
    "get_cluster_interfaces_as_dicts",
]

from maasserver.models import NodeGroupInterface
from maasserver.utils.async import transactional


@transactional
def update_foreign_dhcp_ip(cluster_uuid, interface_name, foreign_dhcp_ip):
    """Update the foreign_dhcp_ip field of a given interface on a cluster.

    Note: We do this through an update, not a read/modify/write.
    Updating NodeGroupInterface client-side may inadvertently trigger
    Django signals that cause a rewrite of the DHCP config, plus restart
    of the DHCP server.  The inadvertent triggering has been known to
    happen because of race conditions between read/modify/write
    transactions that were enabled by Django defaulting to, and being
    designed for, the READ COMMITTED isolation level; the ORM writing
    back even unmodified fields; and GenericIPAddressField's default
    value being prone to problems where NULL is sometimes represented as
    None, sometimes as an empty string, and the difference being enough
    to convince the signal machinery that these fields have changed when
    in fact they have not.
    """
    query = NodeGroupInterface.objects.filter(
        nodegroup__uuid=cluster_uuid, name=interface_name)
    query.update(foreign_dhcp_ip=foreign_dhcp_ip)


@transactional
def get_cluster_interfaces_as_dicts(cluster_uuid):
    """Return all the interfaces on a given cluster as a list of dicts.

    :return: A list of dicts in the form {'name': interface.name, 'ip':
        interface.ip}, one dict per interface on the cluster.
    """
    cluster_interfaces = NodeGroupInterface.objects.filter(
        nodegroup__uuid=cluster_uuid)
    return [
        {b'name': interface.name, b'ip': interface.ip}
        for interface in cluster_interfaces]
