# Copyright 2014-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Power control."""

__all__ = [
    "is_driver_available",
    "power_action_registry",
    "power_state_update",
    "QUERY_POWER_TYPES",
]

from provisioningserver.rpc import getRegionClient
from provisioningserver.rpc.region import UpdateNodePowerState
from provisioningserver.utils.twisted import asynchronous

# List of power_types that support querying the power state.
# change_power_state() will only retry changing the power
# state for these power types.
# This is meant to be temporary until all the power types support
# querying the power state of a node.
QUERY_POWER_TYPES = [
    'amt',
    'hmc',
    'ipmi',
    'mscm',
    'msftocs',
    'sm15k',
    'ucsm',
    'virsh',
    'vmware',
]


# We could use a Registry here, but it seems kind of like overkill.
power_action_registry = {}


def is_driver_available(power_type):
    """Is there a Python-based driver available for the given power type?"""
    from provisioningserver.drivers import power  # Circular import.
    return power.PowerDriverRegistry.get_item(power_type) is not None


@asynchronous
def power_state_update(system_id, state):
    """Report to the region about a node's power state.

    :param system_id: The system ID for the node.
    :param state: Typically "on", "off", or "error".
    """
    client = getRegionClient()
    return client(
        UpdateNodePowerState,
        system_id=system_id,
        power_state=state)
