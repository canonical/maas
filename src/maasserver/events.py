import datetime
import logging

from maasserver.rpc.events import (
    register_event_type,
    send_event,
    send_event_ip_address,
    send_event_mac_address,
)
from maasserver.utils.threads import deferToDatabase
from provisioningserver.events import EVENT_DETAILS, NodeEventHub
from provisioningserver.rpc.exceptions import NoSuchNode
from provisioningserver.utils.env import get_maas_id
from provisioningserver.utils.twisted import (
    asynchronous,
    callOut,
    DeferredValue,
    FOREVER,
    suppress,
)

log = logging.getLogger(__name__)


class RegionEventHub(NodeEventHub):
    @asynchronous
    def registerEventType(self, event_type):
        details = EVENT_DETAILS[event_type]

        d = deferToDatabase(
            register_event_type,
            event_type,
            details.description,
            details.level,
        )

        d.addBoth(callOut, self._types_registering.pop, event_type)
        # On success, record that the event type has been registered. On
        # failure, ensure that the set of registered event types does NOT
        # contain the event type.
        d.addCallbacks(
            callback=callOut,
            callbackArgs=(self._types_registered.add, event_type),
            errback=callOut,
            errbackArgs=(self._types_registered.discard, event_type),
        )
        # Capture the result into a DeferredValue.
        result = DeferredValue()
        result.capture(d)
        # Keep track of it so that concurrent requests don't duplicate work.
        self._types_registering[event_type] = result
        return result.get()

    @asynchronous
    def logByID(self, event_type, system_id, description=""):
        def send(_):
            return deferToDatabase(
                send_event,
                system_id,
                event_type,
                description,
                datetime.now(),
            )

        d = self.ensureEventTypeRegistered(event_type).addCallback(send)
        d.addErrback(self._checkEventTypeRegistered, event_type)
        return d

    @asynchronous
    def logByMac(self, event_type, mac_address, description=""):
        def send(_):
            return deferToDatabase(
                send_event_mac_address,
                mac_address,
                event_type,
                description,
            )

        d = self.ensureEventTypeRegistered(event_type).addCallback(send)
        d.addErrback(self._checkEventTypeRegistered, event_type)
        d.addErrback(suppress, NoSuchNode)
        return d

    @asynchronous
    def logByIP(self, event_type, ip_address, description=""):
        def send(_):
            return deferToDatabase(
                send_event_ip_address,
                ip_address,
                event_type,
                description,
            )

        d = self.ensureEventTypeRegistered(event_type).addCallback(send)
        d.addErrback(self._checkEventTypeRegistered, event_type)

        # Suppress NoSuchNode. This happens during enlistment because the
        # region does not yet know of the node; it's quite normal. Logging
        # tracebacks telling us about it is not useful. Perhaps the region
        # should store these logs anyway. Then, if and when the node is
        # enlisted, logs prior to enlistment can be seen.
        d.addErrback(suppress, NoSuchNode)
        return d


nodeEventHub = RegionEventHub()


@asynchronous
def send_node_event(event_type, system_id, hostname, description=""):
    """Send the given node event to the region.

    :param event_type: The type of the event.
    :type event_type: unicode
    :param system_id: The system ID of the node of the event.
    :type system_id: unicode
    :param hostname: Ignored!
    :param description: An optional description of the event.
    :type description: unicode
    """
    return nodeEventHub.logByID(event_type, system_id, description)


@asynchronous
def send_node_event_mac_address(event_type, mac_address, description=""):
    """Send the given node event to the region for the given mac address.

    :param event_type: The type of the event.
    :type event_type: unicode
    :param mac_address: The MAC Address of the node of the event.
    :type mac_address: unicode
    :param description: An optional description of the event.
    :type description: unicode
    """
    return nodeEventHub.logByMAC(event_type, mac_address, description)


@asynchronous
def send_node_event_ip_address(event_type, ip_address, description=""):
    """Send the given node event to the region for the given IP address.

    :param event_type: The type of the event.
    :type event_type: unicode
    :param ip_address: The IP Address of the node of the event.
    :type ip_address: unicode
    :param description: An optional description of the event.
    :type description: unicode
    """
    return nodeEventHub.logByIP(event_type, ip_address, description)


@asynchronous
def send_rack_event(event_type, description=""):
    """Send an event about the running rack to the region.

    :param event_type: The type of the event.
    :type event_type: unicode
    :param description: An optional description of the event.
    :type description: unicode
    """
    return nodeEventHub.logByID(event_type, get_maas_id(), description)


@asynchronous(timeout=FOREVER)
def try_send_rack_event(event_type, description=""):
    """Try to send a rack event to the region.

    Log something locally if this fails but otherwise supress all
    failures.
    """
    d = send_rack_event(event_type, description)
    d.addErrback(
        log.err,
        "Failure sending rack event to region: %s - %s"
        % (event_type, description),
    )
    return d
