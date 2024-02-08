# Copyright 2014-2021 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""RPC helpers relating to nodes."""


from functools import partial

from twisted.internet import reactor
from twisted.internet.defer import DeferredList, succeed
from twisted.protocols.amp import UnhandledCommand

from maasserver.exceptions import PowerProblem
from maasserver.rpc import getAllClients
from provisioningserver.enum import POWER_STATE
from provisioningserver.logger import get_maas_logger, LegacyLogger
from provisioningserver.rpc.cluster import (
    PowerCycle,
    PowerDriverCheck,
    PowerOff,
    PowerOn,
    PowerQuery,
    SetBootOrder,
)
from provisioningserver.rpc.exceptions import PowerActionAlreadyInProgress
from provisioningserver.utils.twisted import asynchronous, callOut, FOREVER

log = LegacyLogger()
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
    log.debug(
        "{hostname}: Asking rack controller to power on/off node.",
        hostname=hostname,
    )
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
    d = client(
        command,
        system_id=system_id,
        hostname=hostname,
        power_type=power_info.power_type,
        context=power_info.power_parameters,
    )

    def eb_service_unavailable(failure):
        if failure.check(PowerActionAlreadyInProgress):
            raise PowerProblem(str(failure.value))

    d.addErrback(eb_service_unavailable)
    return d


power_off_node = partial(power_node, PowerOff)
power_on_node = partial(power_node, PowerOn)


@asynchronous(timeout=30)
def power_cycle(client, system_id, hostname, power_info):
    """Power cycle the node.

    The power call will be directed to the provided `client`.

    :param client: The `rpc.common.Client` of the rack controller to perform
        the power action.
    :param system_id: The Node's system_id
    :param hostname: The Node's hostname
    :param power_info: A dict containing the power information for the
        node.
    :return: A :py:class:`twisted.internet.defer.Deferred` that will
        fire when the `PowerCycle` call completes.

    """
    log.debug(
        "{hostname}: Asking rack controller(s) to power cycle node.",
        hostname=hostname,
    )
    # We don't strictly care about the result _here_; the outcome of the
    # deferred gets reported elsewhere. However, PowerCycle can return
    # UnknownPowerType and NotImplementedError which are worth knowing
    # about and returning to the caller of this API method, so it's
    # probably worth changing PowerCycle (or adding another call) to return
    # after initial validation but then continue with the power-cycle
    # process. For now we simply return the deferred to the caller so
    # they can choose to chain onto it, or to "cap it off", so that
    # result gets consumed (Twisted will complain if an error is not
    # consumed).
    d = client(
        PowerCycle,
        system_id=system_id,
        hostname=hostname,
        power_type=power_info.power_type,
        context=power_info.power_parameters,
    )

    def eb_service_unavailable(failure):
        if failure.check(PowerActionAlreadyInProgress):
            raise PowerProblem(str(failure.value))

    d.addErrback(eb_service_unavailable)
    return d


@asynchronous(timeout=15)
def power_query(client, system_id, hostname, power_info):
    """Power query the node.

    The power call will be directed to the provided `client`.

    :param client: The `rpc.common.Client` of the rack controller to perform
        the power action.
    :param system_id: The Node's system_id
    :param hostname: The Node's hostname
    :param power_info: A dict containing the power information for the
        node.
    :return: A :py:class:`twisted.internet.defer.Deferred` that will
        fire when the `PowerQuery` call completes.

    """
    log.debug(
        "{hostname}: Asking rack controller(s) to power query node.",
        hostname=hostname,
    )
    # We don't strictly care about the result _here_; the outcome of the
    # deferred gets reported elsewhere. However, PowerQuery can return
    # UnknownPowerType and NotImplementedError which are worth knowing
    # about and returning to the caller of this API method, so it's
    # probably worth changing PowerQuery (or adding another call) to return
    # after initial validation but then continue with the powering-query
    # process. For now we simply return the deferred to the caller so
    # they can choose to chain onto it, or to "cap it off", so that
    # result gets consumed (Twisted will complain if an error is not
    # consumed).
    return client(
        PowerQuery,
        system_id=system_id,
        hostname=hostname,
        power_type=power_info.power_type,
        context=power_info.power_parameters,
    )


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
        log.msg(
            "Unable to query cluster for power packages. Cluster does not"
            "support the PowerDriverCheck RPC method. Returning OK."
        )
        return []

    d = client(PowerDriverCheck, power_type=power_type)
    d.addCallbacks(extract_missing_packages, ignore_unhandled_command)
    return d


def pick_best_power_state(power_states):
    """Return the best power state from `power_states`.

    Selected in order:
        1. On
        2. Off
        3. Error
        4. Unknown
    """
    if POWER_STATE.ON in power_states:
        return POWER_STATE.ON
    if POWER_STATE.OFF in power_states:
        return POWER_STATE.OFF
    if POWER_STATE.ERROR in power_states:
        return POWER_STATE.ERROR
    return POWER_STATE.UNKNOWN


@asynchronous(timeout=FOREVER)
def power_query_all(system_id, hostname, power_info, timeout=60):
    """Query every connected rack controller and get the power status from all
    rack controllers.

    :return: a tuple with the power state for the node and a list of
        rack controller system_id's that responded and a list of rack
        controller system_id's that failed to respond.
    """
    deferreds = []
    call_order = []
    clients = getAllClients()
    for client in clients:
        d = client(
            PowerQuery,
            system_id=system_id,
            hostname=hostname,
            power_type=power_info.power_type,
            context=power_info.power_parameters,
        )
        deferreds.append(d)
        call_order.append(client.ident)

    def cb_result(result):
        power_states = set()
        responded_rack_ids = set()
        failed_rack_ids = set()
        for rack_system_id, (success, response) in zip(call_order, result):
            if success:
                power_state = response["state"]
                if power_state == POWER_STATE.ERROR:
                    # Rack controller cannot access this BMC.
                    failed_rack_ids.add(rack_system_id)
                else:
                    # Rack controller can access this BMC.
                    power_states.add(response["state"])
                    responded_rack_ids.add(rack_system_id)
            else:
                failed_rack_ids.add(rack_system_id)
        return (
            pick_best_power_state(power_states),
            responded_rack_ids,
            failed_rack_ids,
        )

    # Process all defers and build the result.
    dList = DeferredList(deferreds, consumeErrors=True)
    dList.addCallback(cb_result)

    def cancel():
        try:
            dList.cancel()
        except Exception:
            # Don't care about the error.
            pass

    # Create the canceller if timeout provided.
    if timeout is None:
        canceller = None
    else:
        canceller = reactor.callLater(timeout, cancel)

    def done():
        if canceller is not None and canceller.active():
            canceller.cancel()

    # Cancel the canceller once finished.
    dList.addBoth(callOut, done)
    return dList


@asynchronous(timeout=30)
def set_boot_order(client, system_id, hostname, power_info, order):
    """Remotely set the boot order of a specified machine.

    The power call will be directed to the provided `client`.

    :param client: The `rpc.common.Client` of the rack controller to perform
        the power action.
    :param system_id: The Node's system_id
    :param hostname: The Node's hostname
    :param power-info: A dict containing the power information for the
        node.
    :param order: An ordered list representing the boot order.
    :return: A :py:class:`twisted.internet.defer.Deferred` that will
        fire when the `command` call completes. This Defer will return
        the given client.

    """
    # If no order was passed there is nothing for the rack to do. This can
    # happen when the region detects the power driver doesn't support ordering
    if not order:
        return succeed(client)

    log.debug(
        "{hostname}: Asking rack controller to reorder boot order.",
        hostname=hostname,
    )
    d = client(
        SetBootOrder,
        system_id=system_id,
        hostname=hostname,
        power_type=power_info.power_type,
        context=power_info.power_parameters,
        order=order,
    )
    d.addCallback(lambda _: client)

    return d
