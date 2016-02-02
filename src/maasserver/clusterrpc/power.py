# Copyright 2014-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""RPC helpers relating to nodes."""

__all__ = [
    "power_off_node",
    "power_on_node",
]

from functools import partial
import logging

from provisioningserver.logger import get_maas_logger
from provisioningserver.rpc.cluster import (
    PowerDriverCheck,
    PowerOff,
    PowerOn,
)
from provisioningserver.twisted.protocols.amp import UnhandledCommand
from provisioningserver.utils.twisted import asynchronous


logger = logging.getLogger(__name__)
maaslog = get_maas_logger("power")


@asynchronous(timeout=15)
def power_node(command, client, system_id, hostname, power_info):
    """Power-on/off the given nodes.

    The power call will be directed to the provided `client`.

    :param command: The `amp.Command` to call.
    :param client: The `rpc.common.Client` of the rack controller to perform
        the power action.
    :param system_id: The Node's system_id
    :param hostname: The Node's hostname
    :param power-info: A dict containing the power information for the
        node.
    :return: A :py:class:`twisted.internet.defer.Deferred` that will
        fire when the `command` call completes.

    """
    maaslog.debug("%s: Asking rack controller to power on/off node.", hostname)
    # We don't strictly care about the result _here_; the outcome of the
    # deferred gets reported elsewhere. However, PowerOn can return
    # UnknownPowerType and NotImplementedError which are worth knowing
    # about and returning to the caller of this API method, so it's
    # probably worth changing PowerOn (or adding another call) to return
    # after initial validation but then continue with the powering-on
    # process. For now we simply return the deferred to the caller so
    # they can choose to chain onto it, or to "cap it off", so that
    # result gets consumed (Twisted will complain if an error is not
    # consumed).
    return client(
        command, system_id=system_id, hostname=hostname,
        power_type=power_info.power_type,
        context=power_info.power_parameters)


power_off_node = partial(power_node, PowerOff)
power_on_node = partial(power_node, PowerOn)


@asynchronous(timeout=30)
def power_driver_check(client, power_type):
    """Call PowerDriverCheck on a `client` and wait for response.

    :param cleint: The `rpc.common.Client` to use.
    :param power_type: The power type to check on that rack controller.
    :return: A list of missing power drivers for the power_type, if any.

    :raises UnknownPowerType: When the requested power type is not known
        to the RackController.
    :raises NotImplementedError: When the power driver hasn't implemented
        the missing packages check.
    :raises TimeoutError: If a response has not been received within 30
        seconds.
    """
    def extract_missing_packages(response):
        return response["missing_packages"]

    def ignore_unhandled_command(failure):
        failure.trap(UnhandledCommand)
        # The region hasn't been upgraded to support this method yet, so give
        # up. Returning an empty list indicates that the power driver is OK, so
        # the power attempt will continue and any errors will be caught later.
        logger.warn(
            "Unable to query cluster for power packages. Cluster does not"
            "support the PowerDriverCheck RPC method. Returning OK.")
        return []

    d = client(PowerDriverCheck, power_type=power_type)
    d.addCallbacks(extract_missing_packages, ignore_unhandled_command)
    return d
