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
    "power_off_nodes",
    "power_on_nodes",
]

from functools import partial

from maasserver.rpc import getClientFor
from provisioningserver.logger import get_maas_logger
from provisioningserver.rpc.cluster import (
    PowerOff,
    PowerOn,
    )
from provisioningserver.utils.twisted import asynchronous


maaslog = get_maas_logger("power")


@asynchronous(timeout=15)
def power_nodes(command, nodes):
    """Power-on/off the given nodes.

    Nodes can be in any cluster; the power calls will be directed to their
    owning cluster.

    :param command: The `amp.Command` to call.
    :param nodes: A sequence of ``(system-id, hostname, cluster-uuid,
        power-info)`` tuples.
    :returns: A mapping of each node's system ID to a
        :py:class:`twisted.internet.defer.Deferred` that will fire when
        the `command` call completes.

    """
    def call_power_command(client, **kwargs):
        return client(command, **kwargs)

    deferreds = {}
    for node in nodes:
        system_id, hostname, cluster_uuid, power_info = node
        maaslog.debug("%s: Asking cluster to power on", hostname)
        deferreds[system_id] = getClientFor(cluster_uuid).addCallback(
            call_power_command, system_id=system_id, hostname=hostname,
            power_type=power_info.power_type,
            context=power_info.power_parameters)

    # We don't strictly care about the results _here_; their outcomes get
    # reported elsewhere. However, PowerOn can return UnknownPowerType and
    # NotImplementedError which are worth knowing about and returning to the
    # caller of this API method, so it's probably worth changing PowerOn (or
    # adding another call) to return after initial validation but then
    # continue with the powering-on process. For now we simply return the
    # deferreds to the caller so they can choose to chain onto them, or to
    # "cap them off", so that results are consumed (Twisted will complain if
    # an error is not consumed).
    return deferreds


power_off_nodes = partial(power_nodes, PowerOff)
power_on_nodes = partial(power_nodes, PowerOn)
