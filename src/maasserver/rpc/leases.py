# Copyright 2014-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""RPC helpers relating to DHCP leases."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    "update_leases",
]

from maasserver.models.dhcplease import DHCPLease
from maasserver.models.nodegroup import NodeGroup
from maasserver.models.staticipaddress import StaticIPAddress
from maasserver.utils.orm import transactional
from provisioningserver.pserv_services.lease_upload_service import (
    convert_mappings_to_leases,
)
from provisioningserver.rpc.exceptions import NoSuchCluster
from provisioningserver.utils.twisted import synchronous


@synchronous
@transactional
def update_leases(uuid, mappings):
    """Updates DHCP leases on a cluster given the mappings in UpdateLeases.

    :param uuid: Cluster UUID as found in
        :py:class`~provisioningserver.rpc.region.UpdateLeases`.
    :param mappings: List of {<ip>: <mac>} dicts as defined in
        :py:class`~provisioningserver.rpc.region.UpdateLeases`.

    Converts the mappings format into a dict that
    DHCPLease.objects.update_leases needs and then calls it.

    :raises NoSuchCluster: If the cluster identified by `uuid` does not
        exist.
    """
    try:
        nodegroup = NodeGroup.objects.get_by_natural_key(uuid)
    except NodeGroup.DoesNotExist:
        raise NoSuchCluster.from_uuid(uuid)
    else:
        leases = convert_mappings_to_leases(mappings)
        DHCPLease.objects.update_leases(nodegroup, leases)
        StaticIPAddress.objects.update_leases(nodegroup, leases)
        return {}
