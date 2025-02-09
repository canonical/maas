# Copyright 2015-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Utilities for the provisioning server."""

import json

from twisted.internet import reactor
from twisted.internet.defer import inlineCallbacks, returnValue
from twisted.protocols.amp import UnhandledCommand, UnknownRemoteError

from provisioningserver.logger import get_maas_logger
from provisioningserver.rpc import getRegionClient
from provisioningserver.rpc.exceptions import (
    CommissionNodeFailed,
    NoConnectionsAvailable,
    NodeAlreadyExists,
)
from provisioningserver.rpc.region import CreateNode
from provisioningserver.utils.network import coerce_to_valid_hostname
from provisioningserver.utils.twisted import asynchronous, pause, retries

maaslog = get_maas_logger("region")


@asynchronous
@inlineCallbacks
def create_node(
    macs, arch, power_type, power_parameters, domain=None, hostname=None
):
    """Create a Node on the region and return its system_id.

    :param macs: A list of MAC addresses belonging to the node.
    :param arch: The node's architecture, in the form 'arch/subarch'.
    :param power_type: The node's power type as a string.
    :param power_parameters: The power parameters for the node, as a
        dict.
    :param domain: The domain the node should join.
    """
    if hostname is not None:
        hostname = coerce_to_valid_hostname(hostname, False)

    for elapsed, remaining, wait in retries(15, 5, reactor):  # noqa: B007
        try:
            client = getRegionClient()
            break
        except NoConnectionsAvailable:
            yield pause(wait, reactor)
    else:
        maaslog.error("Can't create node, no RPC connection to region.")
        return

    # De-dupe the MAC addresses we pass. We sort here to avoid test
    # failures.
    macs = sorted(set(macs))
    try:
        response = yield client(
            CreateNode,
            architecture=arch,
            power_type=power_type,
            power_parameters=json.dumps(power_parameters),
            mac_addresses=macs,
            hostname=hostname,
            domain=domain,
        )
    except NodeAlreadyExists:
        # The node already exists on the region, so we log the error and
        # give up.
        maaslog.error(
            "A node with one of the mac addresses in %s already exists.", macs
        )
        returnValue(None)
    except UnhandledCommand:
        # The region hasn't been upgraded to support this method
        # yet, so give up.
        maaslog.error(
            "Unable to create node on region: Region does not "
            "support the CreateNode RPC method."
        )
        returnValue(None)
    except UnknownRemoteError as e:
        # This happens, for example, if a ValidationError occurs on the region.
        # (In particular, we see this if the hostname is a duplicate.)
        # We should probably create specific exceptions for these, so we can
        # act on them appropriately.
        maaslog.error(
            "Unknown error while creating node %s: %s (see regiond.log)",
            macs,
            e.description,
        )
        returnValue(None)
    else:
        returnValue(response["system_id"])


@asynchronous
@inlineCallbacks
def commission_node(system_id, user):
    """Commission a Node on the region.

    :param system_id: system_id of node to commission.
    :param user: user for the node.
    """
    # Avoid circular dependencies.
    from provisioningserver.rpc.region import CommissionNode

    for elapsed, remaining, wait in retries(15, 5, reactor):  # noqa: B007
        try:
            client = getRegionClient()
            break
        except NoConnectionsAvailable:
            yield pause(wait, reactor)
    else:
        maaslog.error("Can't commission node, no RPC connection to region.")
        return

    try:
        yield client(CommissionNode, system_id=system_id, user=user)
    except CommissionNodeFailed as e:
        # The node cannot be commissioned, give up.
        maaslog.error(
            "Could not commission with system_id %s because %s.",
            system_id,
            e.args[0],
        )
    except UnhandledCommand:
        # The region hasn't been upgraded to support this method
        # yet, so give up.
        maaslog.error(
            "Unable to commission node on region: Region does not "
            "support the CommissionNode RPC method."
        )
    finally:
        returnValue(None)
