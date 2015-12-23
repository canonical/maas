# Copyright 2014-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""RPC helpers relating to DHCP leases."""

__all__ = [
    "update_leases",
]

from maasserver.models.nodegroup import NodeGroup
from maasserver.models.staticipaddress import StaticIPAddress
from maasserver.utils.orm import transactional
from provisioningserver.rpc.exceptions import NoSuchCluster
from provisioningserver.utils.twisted import synchronous


def convert_mappings_to_leases(mappings):
    """Convert AMP mappings to record_lease_state() leases.

    Take mappings, as used by UpdateLeases, and turn into leases
    as used by record_lease_state().
    """
    return [
        (mapping["ip"], mapping["mac"])
        for mapping in mappings
    ]


@synchronous
@transactional
def update_leases(uuid, mappings):
    """Updates DHCP leases on a cluster given the mappings in UpdateLeases.

    :param uuid: Cluster UUID as found in
        :py:class`~provisioningserver.rpc.region.UpdateLeases`.
    :param mappings: List of {<ip>: <mac>} dicts as defined in
        :py:class`~provisioningserver.rpc.region.UpdateLeases`.

    Converts the mappings format into a dict that
    StaticIPAddress.objects.update_leases needs and then calls it.

    :raises NoSuchCluster: If the cluster identified by `uuid` does not
        exist.
    """
    try:
        nodegroup = NodeGroup.objects.get_by_natural_key(uuid)
    except NodeGroup.DoesNotExist:
        raise NoSuchCluster.from_uuid(uuid)
    else:
        leases = convert_mappings_to_leases(mappings)
        StaticIPAddress.objects.update_leases(nodegroup, leases)
        return {}


@synchronous
@transactional
def update_lease(
        cluster_uuid, action, mac, ip_family, ip, timestamp,
        lease_time=None, hostname=None):
    """Update one DHCP leases from a cluster.

    :param cluster_uuid: Cluster UUID as found in
        :py:class`~provisioningserver.rpc.region.UpdateLease`.
    :param action: DHCP action taken on the cluster as found in
        :py:class`~provisioningserver.rpc.region.UpdateLease`.
    :param mac: MAC address for the action taken on the cluster as found in
        :py:class`~provisioningserver.rpc.region.UpdateLease`.
    :param ip_family: IP address family for the action taken on the cluster as
        found in :py:class`~provisioningserver.rpc.region.UpdateLease`.
    :param ip: IP address for the action taken on the cluster as found in
        :py:class`~provisioningserver.rpc.region.UpdateLease`.
    :param timestamp: Epoch time for the action taken on the cluster as found
        in :py:class`~provisioningserver.rpc.region.UpdateLease`.
    :param lease_time: Legth of the lease on the cluster as found in
        :py:class`~provisioningserver.rpc.region.UpdateLease`.
    :param hostname: Hostname of the machine for the lease on the cluster as
        found in :py:class`~provisioningserver.rpc.region.UpdateLease`.

    Based on the action a DISCOVERED StaticIPAddress will be either created or
    updated for a Interface that matches `mac`.

    Actions:
        commit -  When a new lease is given to a client. `lease_time` is
                  required for this action. `hostname` is optional.
        expiry -  When a lease has expired. Occurs when a client fails to renew
                  their lease before the end of the `lease_time`.
        release - When a client explicitly releases the lease.

    :raises NoSuchCluster: If the cluster identified by `cluster_uuid` does not
        exist.
    """
    try:
        NodeGroup.objects.get_by_natural_key(cluster_uuid)
    except NodeGroup.DoesNotExist:
        raise NoSuchCluster.from_uuid(cluster_uuid)

    # TODO blake_r: Update the lease in StaticIPAddress table.
    return {}
