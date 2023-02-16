# Copyright 2016-2017 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Networks monitoring service."""


from abc import ABCMeta, abstractmethod
from collections import OrderedDict
from datetime import timedelta
import functools
import json
from json.decoder import JSONDecodeError
import os
from pathlib import Path
from pprint import pformat
import re
import socket
import struct
import time

from netaddr import IPAddress
from twisted.application.internet import TimerService
from twisted.application.service import MultiService
from twisted.internet.defer import Deferred, inlineCallbacks, maybeDeferred
from twisted.internet.error import ProcessDone, ProcessTerminated
from twisted.internet.interfaces import IReactorMulticast
from twisted.internet.protocol import DatagramProtocol, ProcessProtocol
from twisted.internet.threads import deferToThread
from zope.interface.exceptions import Invalid
from zope.interface.verify import verifyObject

from provisioningserver.config import is_dev_environment
from provisioningserver.logger import get_maas_logger, LegacyLogger
from provisioningserver.refresh import refresh
from provisioningserver.refresh.node_info_scripts import (
    COMMISSIONING_OUTPUT_NAME,
)
from provisioningserver.utils.beaconing import (
    age_out_uuid_queue,
    BEACON_IPV4_MULTICAST,
    BEACON_IPV6_MULTICAST,
    BEACON_PORT,
    beacon_to_json,
    create_beacon_payload,
    read_beacon_payload,
    ReceivedBeacon,
    TopologyHint,
)
from provisioningserver.utils.fs import get_maas_common_command, NamedLock
from provisioningserver.utils.network import (
    enumerate_ipv4_addresses,
    get_all_interfaces_definition,
    get_default_monitored_interfaces,
)
from provisioningserver.utils.shell import get_env_with_bytes_locale
from provisioningserver.utils.twisted import (
    callOut,
    deferred,
    pause,
    terminateProcess,
)

maaslog = get_maas_logger("networks.monitor")
log = LegacyLogger()


class JSONPerLineProtocol(ProcessProtocol):
    """ProcessProtocol which parses a single JSON object per line of text.

    This expects that a UTF-8 locale is used, i.e. that text written to stdout
    and stderr by the spawned process uses the UTF-8 character set.
    """

    def __init__(self, callback):
        super().__init__()
        self._callback = callback
        self.done = Deferred()

    def connectionMade(self):
        super().connectionMade()
        self._outbuf = b""
        self._errbuf = b""

    def outReceived(self, data):
        lines, self._outbuf = self.splitLines(self._outbuf + data)
        for line in lines:
            self.outLineReceived(line)

    def errReceived(self, data):
        lines, self._errbuf = self.splitLines(self._errbuf + data)
        for line in lines:
            self.errLineReceived(line)

    @staticmethod
    def splitLines(data):
        lines = data.splitlines(True)
        if len(lines) == 0:
            # Nothing to do.
            remaining = b""
        elif lines[-1].endswith(b"\n"):
            # All lines are complete.
            remaining = b""
        else:
            # The last line is incomplete.
            remaining = lines.pop()
        return lines, remaining

    def outLineReceived(self, line):
        line = line.decode("utf-8")
        try:
            obj = json.loads(line)
        except JSONDecodeError:
            log.msg("Failed to parse JSON: %r" % line)
        else:
            self.objectReceived(obj)

    def objectReceived(self, obj):
        self._callback([obj])

    def errLineReceived(self, line):
        line = line.decode("utf-8")
        log.msg(line.rstrip())

    def processEnded(self, reason):
        if len(self._errbuf) != 0:
            self.errLineReceived(self._errbuf)
        # If the process finished normally, fire _done with
        # None. Otherwise, pass the reason through.
        if reason.check(ProcessDone):
            self.done.callback(None)
        else:
            self.done.errback(reason)


class ProtocolForObserveARP(JSONPerLineProtocol):
    """Protocol used when spawning `maas-rack observe-arp`.

    The difference between `JSONPerLineProtocol` and `ProtocolForObserveARP`
    is that the neighbour observation protocol needs to insert the interface
    metadata into the resultant object before the callback.
    """

    def __init__(self, interface, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.interface = interface

    def objectReceived(self, obj):
        obj["interface"] = self.interface
        super().objectReceived(obj)

    def errLineReceived(self, line):
        line = line.decode("utf-8").rstrip()
        log.msg("observe-arp[%s]:" % self.interface, line)


class ProtocolForObserveBeacons(JSONPerLineProtocol):
    """Protocol used when spawning `maas-rack observe-beacons`.

    The difference between `JSONPerLineProtocol` and
    `ProtocolForObserveBeacons` is that the beacon observation protocol needs
    to insert the interface metadata into the resultant object before the
    callback.
    """

    def __init__(self, interface, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.interface = interface

    def objectReceived(self, obj):
        obj["interface"] = self.interface
        super().objectReceived(obj)

    def errLineReceived(self, line):
        line = line.decode("utf-8").rstrip()
        log.msg("observe-beacons[%s]:" % self.interface, line)


class ProtocolForObserveMDNS(JSONPerLineProtocol):
    """Protocol used when spawning `maas-rack observe-mdns`.

    This ensures that the spawned process is configured as a process group
    leader for its own process group.

    The spawned process is assumed to be `avahi-browse` which prints a
    somewhat inane "Got SIG***, quitting" message when signalled. We do want
    to see if it has something useful to say so we filter out lines from
    stderr matching this pattern. Other lines are logged with the prefix
    "observe-mdns".
    """

    _re_ignore_stderr = re.compile("^Got SIG[A-Z]+, quitting[.]")

    def errLineReceived(self, line):
        line = line.decode("utf-8").rstrip()
        if self._re_ignore_stderr.match(line) is None:
            log.msg("observe-mdns:", line)


class ProcessProtocolService(TimerService, metaclass=ABCMeta):
    def __init__(self, interval=60.0, clock=None, reactor=None):
        super().__init__(interval, self.startProcess)
        self._process = self._protocol = None
        self._stopping = False
        self.reactor = reactor
        if self.reactor is None:
            from twisted.internet import reactor

            self.reactor = reactor
        self.clock = clock
        if self.clock is None:
            self.clock = self.reactor

    @deferred
    def startProcess(self):
        env = get_env_with_bytes_locale()
        log.msg("%s started." % self.getDescription())
        args = self.getProcessParameters()
        assert all(
            isinstance(arg, bytes) for arg in args
        ), "Process arguments must all be bytes, got: %s" % repr(args)
        self._protocol = self.createProcessProtocol()
        self._process = self.reactor.spawnProcess(
            self._protocol, args[0], args, env=env
        )
        return self._protocol.done.addBoth(self._processEnded)

    def _processEnded(self, failure):
        if failure is None:
            log.msg("%s ended normally." % self.getDescription())
        elif failure.check(ProcessTerminated) and self._stopping:
            log.msg("%s was terminated." % self.getDescription())
        else:
            log.err(failure, "%s failed." % self.getDescription())

    @abstractmethod
    def getProcessParameters(self):
        """Return the parameters for the subprocess to launch.

        This MUST be overridden in subclasses.
        """

    @abstractmethod
    def getDescription(self):
        """Return the description of this process, suitable to use in verbose
        logging.

        This MUST be overridden in subclasses.
        """

    @abstractmethod
    def createProcessProtocol(self):
        """
        Creates and returns the ProcessProtocol that will be used to
        communicate with the process.

        This MUST be overridden in subclasses.
        """

    def startService(self):
        """Starts the neighbour observation service."""
        self._stopping = False
        return super().startService()

    def stopService(self):
        """Stops the neighbour observation service."""
        self._stopping = True
        if self._process is not None and self._process.pid is not None:
            terminateProcess(self._process.pid, self._protocol.done)
        return super().stopService()


class NeighbourDiscoveryService(ProcessProtocolService):
    """Service to spawn the per-interface device discovery subprocess."""

    def __init__(self, ifname: str, callback: callable):
        self.ifname = ifname
        self.callback = callback
        super().__init__()

    def getDescription(self) -> str:
        return "Neighbour observation process for %s" % self.ifname

    def getProcessParameters(self):
        maas_rack_cmd = get_maas_common_command().encode("utf-8")
        return [maas_rack_cmd, b"observe-arp", self.ifname.encode("utf-8")]

    def createProcessProtocol(self):
        return ProtocolForObserveARP(self.ifname, callback=self.callback)


class BeaconingService(ProcessProtocolService):
    """Service to spawn the per-interface device discovery subprocess."""

    def __init__(self, ifname: str, callback: callable):
        self.ifname = ifname
        self.callback = callback
        super().__init__()

    def getDescription(self) -> str:
        return "Beaconing process for %s" % self.ifname

    def getProcessParameters(self):
        maas_rack_cmd = get_maas_common_command().encode("utf-8")
        return [maas_rack_cmd, b"observe-beacons", self.ifname.encode("utf-8")]

    def createProcessProtocol(self):
        return ProtocolForObserveBeacons(self.ifname, callback=self.callback)


class MDNSResolverService(ProcessProtocolService):
    """Service to spawn the per-interface device discovery subprocess."""

    def __init__(self, callback):
        self.callback = callback
        super().__init__()

    def getDescription(self):
        return "mDNS observation process"

    def getProcessParameters(self):
        maas_rack_cmd = get_maas_common_command().encode("utf-8")
        return [maas_rack_cmd, b"observe-mdns"]

    def createProcessProtocol(self):
        return ProtocolForObserveMDNS(callback=self.callback)


def interface_info_to_beacon_remote_payload(ifname, ifdata, rx_vid=None):
    """Converts the specified interface information entry to a beacon payload.

    :param ifname: The name of the interface.
        (The key from `get_all_interfaces_definition()`.)
    :param ifdata: The information for the interface.
        (The value from `get_all_interfaces_definition()`.)
    :param rx_vid: The VID this beacon is being sent or received on.
        If missing (or zero), this indicates unknown/untagged.
    :return: A subset of the ifdata, with the addition of the 'name' key,
        which will be set to the given `ifname`.
    """
    # copy network info, filtering out unneeded fields
    remote = {
        key: value
        for key, value in ifdata.items()
        if key not in ("enabled", "monitored", "links", "source")
    }
    if ifname is not None:
        remote["name"] = ifname
    # The subnet will be replaced by the value of each subnet link, but if
    # no link is configured, None is the default.
    remote["subnet"] = None
    if rx_vid is not None:
        remote["vid"] = rx_vid
    return remote


def set_ipv4_multicast_source_address(sock, source_address):
    """Sets the given socket up to send multicast from the specified source.

    Ensures the multicast TTL is set to 1, so that packets are not forwarded
    beyond the local link.

    :param sock: An opened IP socket.
    :param source_address: A string representing an IPv4 source address.
    """
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 1)
    sock.setsockopt(
        socket.IPPROTO_IP,
        socket.IP_MULTICAST_IF,
        socket.inet_aton(source_address),
    )


def set_ipv6_multicast_source_ifindex(sock, ifindex):
    """Sets the given socket up to send multicast from the specified source.

    Ensures the multicast hop limit is set to 1, so that packets are not
    forwarded beyond the local link.

    :param sock: An opened IP socket.
    :param ifindex: An integer representing the interface index.
    """
    sock.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_MULTICAST_HOPS, 1)
    packed_ifindex = struct.pack("I", ifindex)
    sock.setsockopt(
        socket.IPPROTO_IPV6, socket.IPV6_MULTICAST_IF, packed_ifindex
    )


def join_ipv6_beacon_group(sock, ifindex):
    """Joins the MAAS IPv6 multicast group using the specified UDP socket.

    :param sock: An opened IPv6 UDP socket.
    :param ifindex: The interface index that should join the multicast group.
    """
    # XXX mpontillo 2017-06-21: Twisted doesn't support IPv6 here yet.
    # It would be nice to do this:
    # transport.joinGroup(BEACON_IPV6_MULTICAST)
    ipv6_join_sockopt_args = socket.inet_pton(
        socket.AF_INET6, BEACON_IPV6_MULTICAST
    ) + struct.pack("I", ifindex)
    try:
        sock.setsockopt(
            socket.IPPROTO_IPV6, socket.IPV6_JOIN_GROUP, ipv6_join_sockopt_args
        )
    except OSError:
        # Do this on a best-effort basis. We might get an "Address already in
        # use" error if the group is already joined, or (for whatever reason)
        # it is not possible to join a multicast group using this interface.
        pass


def set_ipv6_multicast_loopback(sock, loopback):
    """Sets IPv6 multicast loopback mode on the specified UDP socket.

    This isn't used in MAAS under normal circumstances, but it is useful for
    testing.

    :param sock: An opened IPv6 UDP socket.
    :param loopback: If True, will set up the socket to loop back transmitted
        multicast to the receive path.
    """
    sock.setsockopt(
        socket.IPPROTO_IPV6,
        socket.IPV6_MULTICAST_LOOP,
        struct.pack("I", 1 if loopback else 0),
    )


class BeaconingSocketProtocol(DatagramProtocol):
    """Protocol to handle beaconing packets received from the socket layer."""

    def __init__(
        self,
        reactor,
        process_incoming=False,
        debug=False,
        interface="::",
        loopback=False,
        port=BEACON_PORT,
        interfaces=None,
    ):
        super().__init__()
        self.interface = interface
        self.loopback = loopback
        self.port = port
        if interfaces is None:
            # The interfaces list is used to join multicast groups, so if it
            # wasn't passed in, don't join any.
            interfaces = {}
        self.interfaces = interfaces
        self.reactor = reactor
        self.process_incoming = process_incoming
        self.debug = debug
        # These queues keep track of beacons that have recently been sent
        # or received by the protocol. Ordering is needed here so that we can
        # later age out the least-recently-added packets without traversing the
        # entire dictionary.
        self.tx_queue = OrderedDict()
        self.rx_queue = OrderedDict()
        self.topology_hints = OrderedDict()
        self.listen_port = None
        self.mcast_requested = False
        self.mcast_solicitation = False
        self.last_solicited_mcast = 0
        self._join_multicast_groups()

    def _join_multicast_groups(self):
        try:
            # Need to ensure that the passed-in reactor is, in fact, a "real"
            # reactor, and not None, or a mock reactor used in tests.
            verifyObject(IReactorMulticast, self.reactor)
        except Invalid:
            return
        if self.listen_port is None:
            self.listen_port = self.reactor.listenMulticast(
                self.port, self, interface=self.interface, listenMultiple=True
            )
        sock = self.transport.getHandle()
        if self.loopback:
            # This is only necessary for testing.
            self.transport.setLoopbackMode(self.loopback)
            set_ipv6_multicast_loopback(sock, self.loopback)
            self.transport.joinGroup(
                BEACON_IPV4_MULTICAST, interface="127.0.0.1"
            )
            # Loopback interface always has index 1.
            join_ipv6_beacon_group(sock, 1)
        for ifname, ifdata in self.interfaces.items():
            # Always try to join the IPv6 group on each interface.
            join_ipv6_beacon_group(sock, socket.if_nametoindex(ifname))
            # Merely joining the group with the default parameters is not
            # enough, since we want to join the group on *all* interfaces.
            # So we need to join each group using an assigned IPv4 address
            # on each Ethernet interface.
            for ip in enumerate_ipv4_addresses(ifdata):
                self.transport.joinGroup(BEACON_IPV4_MULTICAST, interface=ip)
                # Use the first IP address on each interface. Since the
                # underlying interface is the same, joining using a
                # secondary IP address on the same interface will produce
                # an "Address already in use" error.
                break

    def updateInterfaces(self, interfaces):
        self.interfaces = interfaces
        self._join_multicast_groups()

    def getAllTopologyHints(self):
        """Returns the set of unique topology hints."""
        # When beaconing runs, hints attached to individual packets might
        # come to the same conclusion about the implied fabric connectivity.
        # Use a set to prevent the region from processing duplicate hints.
        all_hints = set()
        for hints in self.topology_hints.values():
            all_hints |= hints
        return all_hints

    def stopProtocol(self):
        super().stopProtocol()
        if self.listen_port is not None:
            return self.listen_port.stopListening()
        return None

    def send_beacon(self, beacon, destination_address):
        """Send a beacon to the specified destination.

        :param beacon: The `BeaconPayload` namedtuple to send. Must have a
            `payload` ivar containing a 'uuid' element.
        :param destination_address: The UDP/IP (destination, port) tuple. IPv4
            addresses must be in IPv4-mapped IPv6 format.
        :return: True if the beacon was sent, False otherwise.
        """
        try:
            self.transport.write(beacon.bytes, destination_address)
            # If the packet cannot be sent for whatever reason, OSError will
            # be raised, and we won't record sending a beacon we didn't
            # actually send.
            uuid = beacon.payload["uuid"]
            self.tx_queue[uuid] = beacon
            age_out_uuid_queue(self.tx_queue)
            return True
        except OSError as e:
            if self.debug:
                log.msg(
                    "Error while sending beacon to %r: %s"
                    % (destination_address, e)
                )
        return False

    def send_multicast_beacon(self, source, beacon, port=BEACON_PORT):
        """Sends out a multicast beacon from the specified source.

        :param source: The source address of the beacon. If specified as a text
            string, will assume an IPv4 address was specified. If an integer
            was specified, IPv6 is assumed, and the integer will be interpreted
            as an interface index.
        :param beacon: The beacon bytes to send (as the UDP payload).
        :param port: The destination port of the beacon. (optional)
        """
        # Sending multicast to a particular interface requires setting socket
        # options on the socket that Twisted has opened for us. Twisted itself
        # only support selection of IPv4 interfaces, so there are a few extra
        # hoops to jump through here.
        sock = self.transport.getHandle()
        if isinstance(source, str):
            set_ipv4_multicast_source_address(sock, source)
            # We're sending to an IPv4 multicast address using an IPv6 socket
            # in IPv4-compatible mode.
            destination_ip = "::ffff:" + BEACON_IPV4_MULTICAST
        else:
            set_ipv6_multicast_source_ifindex(sock, source)
            destination_ip = BEACON_IPV6_MULTICAST
        self.send_beacon(beacon, (destination_ip, port))

    def send_multicast_beacons(
        self, interfaces, beacon_type="solicitation", verbose=False
    ):
        """Sends out multicast beacons on each interface in `interfaces`.

        :param interfaces: The output of `get_all_interfaces_definition()`.
        :param beacon_type: Type of beacon to send. (Default: 'solicitation'.)
        :param verbose: If True, will log the payload of each beacon sent.
        """
        for ifname, ifdata in interfaces.items():
            if not ifdata["enabled"]:
                continue
            if self.debug:
                log.msg(f"Sending multicast beacon on '{ifname}'.")
            remote = interface_info_to_beacon_remote_payload(ifname, ifdata)
            # We'll make slight adjustments to the beacon payload depending
            # on the configured source subnet (if any), but the basic payload
            # is ready.
            payload = {"remote": remote}
            if_index = socket.if_nametoindex(ifname)
            links = ifdata["links"]
            if not links:
                # No configured links, so try sending out a link-local IPv6
                # multicast beacon.
                beacon = create_beacon_payload(beacon_type, payload)
                if verbose:
                    log.msg("Beacon payload:\n%s" % pformat(beacon.payload))
                self.send_multicast_beacon(if_index, beacon)
                continue
            sent_ipv6 = False
            for link in ifdata["links"]:
                subnet = link["address"]
                remote["subnet"] = subnet
                address = subnet.split("/")[0]
                beacon = create_beacon_payload(beacon_type, payload)
                if verbose:
                    log.msg("Beacon payload:\n%s" % pformat(beacon.payload))
                if ":" not in address:
                    # An IPv4 socket requires the source address to be the
                    # IPv4 address assigned to the interface.
                    self.send_multicast_beacon(address, beacon)
                else:
                    # An IPv6 socket requires the source address to be the
                    # interface index.
                    self.send_multicast_beacon(if_index, beacon)
                    sent_ipv6 = True
            if not sent_ipv6:
                remote["subnet"] = None
                beacon = create_beacon_payload(beacon_type, payload)
                self.send_multicast_beacon(if_index, beacon)

    def solicitationReceived(self, beacon: ReceivedBeacon):
        """Called whenever a solicitation beacon is received.

        Replies to each soliciation with a corresponding advertisement.
        """
        remote = interface_info_to_beacon_remote_payload(
            beacon.ifname, beacon.ifinfo, rx_vid=beacon.vid
        )
        # Construct the reply payload.
        payload = {"remote": remote, "acks": beacon.uuid}
        reply = create_beacon_payload("advertisement", payload)
        self.send_beacon(reply, beacon.reply_address)
        if len(self.interfaces) > 0:
            self.queueMulticastBeaconing()

    def dequeueMulticastBeaconing(self):
        """
        Callback to send multicast beacon advertisements.

        See `queueMulticastAdvertisement`, which schedules this method to run.
        """
        mtime = time.monotonic()
        beacon_type = (
            "solicitation" if self.mcast_solicitation else "advertisement"
        )
        if self.debug:
            log.msg("Sending multicast beacon %ss." % beacon_type)
        self.send_multicast_beacons(self.interfaces, beacon_type)
        self.last_solicited_mcast = mtime
        self.mcast_requested = False
        self.mcast_solicitation = False

    def queueMulticastBeaconing(self, solicitation=False):
        """
        Requests that multicast advertisements be sent out on every interface.

        Ensures that advertisements will not be sent more than once every
        five seconds.

        :param solicitation: If true, sends solicitations rather than
            advertisements. Solicitations are used to initiate "full beaconing"
            with peers; advertisements do not generate beacon replies.
        """
        if solicitation:
            self.mcast_solicitation = True
        if self.mcast_requested:
            # A multicast advertisement has been requested already.
            return
        mtime = time.monotonic()
        # Ensure the minimum time between multicast replies is 5 seconds.
        if mtime > self.last_solicited_mcast + 5:
            timeout = 0
        else:
            timeout = max(mtime - self.last_solicited_mcast, 5)
        self.mcast_requested = True
        self.reactor.callLater(timeout, self.dequeueMulticastBeaconing)

    def processTopologyHints(self, rx: ReceivedBeacon):
        """
        Called when a beacon received, in order to infer network topology.

        :param rx: The `ReceivedBeacon` namedtuple.
        """
        age_out_uuid_queue(self.topology_hints)
        hints = self.topology_hints.get(rx.uuid, set())
        # From what we know so far, we can infer some facts about the network,
        # assuming we received a multicast beacon. (Unicast beacons cannot
        # be used to infer fabric connectivity, since they could have been
        # forwarded by a router).
        # (1) If we received our own beacon, that means the interface we sent
        # the packet out on is on the same fabric as the interface that
        # received it.
        own_beacon = rx.json.get("own_beacon", False)
        if rx.multicast and own_beacon:
            self._add_own_beacon_hints(hints, rx)
        # (2) If we receive a duplicate beacon on two different interfaces,
        # that means those two interfaces are on the same fabric.
        is_dup = rx.json.get("is_dup", False)
        if rx.multicast and is_dup:
            self._add_duplicate_beacon_hints(hints, rx)
        remote_ifinfo = rx.json.get("payload", {}).get("remote", None)
        if remote_ifinfo is not None and not own_beacon:
            self._add_remote_fabric_hints(hints, remote_ifinfo, rx)
        if hints:
            self.topology_hints[rx.uuid] = hints
            if self.debug:
                all_hints = self.getAllTopologyHints()
                log.msg("Topology hint summary:\n%s" % pformat(all_hints))

    def _add_remote_fabric_hints(self, hints, remote_ifinfo, rx):
        """Adds hints for remote networks that are either on-link or routable.

        Since MAAS only uses link-local multicast, we can assume that multicast
        beacons indicate an on-link network. If a unicast beacon was received,
        we can assume that the two endpoints are mutually routable.
        """
        remote_ifname = remote_ifinfo.get("name")
        remote_vid = remote_ifinfo.get("vid")
        remote_mac = remote_ifinfo.get("mac_address")
        hint = "on_remote_network" if rx.multicast else "routable_to"
        if remote_ifname is not None and remote_mac is not None:
            hints.add(
                TopologyHint(
                    rx.ifname,
                    rx.vid,
                    hint,
                    remote_ifname,
                    remote_vid,
                    remote_mac,
                )
            )

    def _add_duplicate_beacon_hints(self, hints, rx):
        """Adds hints regarding duplicate beacons received.

        If a duplicate beacon is received, we can infer that each interface
        that received the beacon is on the same fabric.
        """
        if rx.ifname is not None:
            received_beacons = self.rx_queue.get(rx.uuid, [])
            duplicate_interfaces = set()
            for beacon in received_beacons:
                if beacon.ifname is not None:
                    duplicate_interfaces.add((beacon.ifname, beacon.vid))
                if len(duplicate_interfaces) > 1:
                    # The same beacon was received on more than one interface.
                    for ifname1, vid1 in duplicate_interfaces:
                        for ifname2, vid2 in duplicate_interfaces:
                            if ifname1 == ifname2 and vid1 == vid2:
                                continue
                            hints.add(
                                TopologyHint(
                                    ifname1,
                                    vid1,
                                    "same_local_fabric_as",
                                    ifname2,
                                    vid2,
                                    None,
                                )
                            )

    def _add_own_beacon_hints(self, hints, rx):
        """Adds hints regarding own beacons received.

        If we receive our own beacon, it either means we have two interfaces
        on the same fabric, or a misconfiguration has occurred.
        """
        if rx.ifname is not None:
            # We received our own solicitation.
            sent_beacon = self.tx_queue.get(rx.uuid, None)
            if sent_beacon is not None:
                sent_ifname = sent_beacon.payload.get("remote", {}).get("name")
                if sent_ifname == rx.ifname:
                    # Someone sent us our own beacon. This indicates a network
                    # misconfiguration such as a loop/broadcast storm, or
                    # a malicious attack.
                    hints.add(
                        TopologyHint(
                            sent_ifname,
                            None,
                            "rx_own_beacon_on_tx_interface",
                            rx.ifname,
                            rx.vid,
                            None,
                        )
                    )
                else:
                    hints.add(
                        TopologyHint(
                            sent_ifname,
                            None,
                            "rx_own_beacon_on_other_interface",
                            rx.ifname,
                            rx.vid,
                            None,
                        )
                    )

    def advertisementReceived(self, beacon: ReceivedBeacon):
        """Called when an advertisement beacon is received."""
        pass

    def beaconReceived(self, beacon_json):
        """Called whenever a beacon is received.

        This method is responsible for updating the `tx_queue` and `rx_queue`
        data structures, and determining if the incoming beacon is meaningful
        for determining network topology.

        :param beacon_json: The normalized beacon JSON, which can come either
            from the external tcpdump-based process, or from the sockets layer
            (with less information about the received packet).
        """
        beacon = self.make_ReceivedBeacon(beacon_json)
        if beacon.uuid is None:
            if self.debug:
                log.msg(
                    "Rejecting incoming beacon: no UUID found: \n%s"
                    % (pformat(beacon_json))
                )
            return
        own_beacon = False
        if beacon.uuid in self.tx_queue:
            own_beacon = True
        beacon_json["own_beacon"] = own_beacon
        is_dup = self.remember_beacon_and_check_duplicate(beacon)
        beacon_json["is_dup"] = is_dup
        if self.debug:
            log.msg(
                "%s %sreceived:\n%s"
                % (
                    "Own beacon" if own_beacon else "Beacon",
                    "(duplicate) " if is_dup else "",
                    beacon_json,
                )
            )
        beacon_type = beacon_json["type"]
        self.processTopologyHints(beacon)
        if own_beacon:
            # No need to reply to our own beacon. We already know we received
            # it, and we already acted on that when we processed the hints.
            return
        if beacon_type == "solicitation":
            self.solicitationReceived(beacon)
        elif beacon_type == "advertisement":
            self.advertisementReceived(beacon)

    def make_ReceivedBeacon(self, beacon_json) -> ReceivedBeacon:
        """
        Creates a ReceivedBeacon object to organize the specified beacon JSON.

        :param beacon_json: received beacon JSON
        :return: `ReceivedBeacon` namedtuple
        """
        reply_ip = beacon_json["source_ip"]
        reply_port = beacon_json["source_port"]
        if ":" not in reply_ip:
            # Since we opened an IPv6-compatible socket, need IPv6 syntax
            # here to send to IPv4 addresses.
            reply_ip = "::ffff:" + reply_ip
        reply_address = (reply_ip, reply_port)
        destination_ip = beacon_json.get("destination_ip")
        multicast = False
        if destination_ip is not None:
            ip = IPAddress(destination_ip)
            multicast = ip.is_multicast()
        uuid = beacon_json.get("payload", {}).get("uuid")
        ifname = beacon_json.get("interface")
        ifinfo = self.interfaces.get(ifname, {})
        vid = beacon_json.get("vid")
        beacon = ReceivedBeacon(
            uuid, beacon_json, ifname, ifinfo, vid, reply_address, multicast
        )
        return beacon

    def remember_beacon_and_check_duplicate(self, beacon: ReceivedBeacon):
        """Records an incoming beacon based on its UUID and JSON.

        Organizes incoming beacons in the `rx_queue` by creating a list of
        beacons received [on different interfaces] per UUID.

        :param beacon: The incoming beacon (a ReceivedBeacon namedtuple).
        :return: True if the beacon was a duplicate, otherwise False.
        """
        duplicate_received = False
        # Need to age out before doing anything else; we don't want to match
        # a duplicate packet and then delete it immediately after.
        age_out_uuid_queue(self.rx_queue)
        rx_packets_for_uuid = self.rx_queue.get(beacon.uuid, [])
        if len(rx_packets_for_uuid) > 0:
            duplicate_received = True
        rx_packets_for_uuid.append(beacon)
        self.rx_queue[beacon.uuid] = rx_packets_for_uuid
        return duplicate_received

    def get_receive_interface_info(self, context):
        """Returns a dictionary representing information about the receive
        interface, given the context of the beacon. The context can be the
        limited information received from the socket layer, or the extended
        information from the monitoring process.
        """
        receive_interface_info = {
            "name": context.get("interface"),
            "source_ip": context.get("source_ip"),
            "destination_ip": context.get("destination_ip"),
            "source_mac": context.get("source_mac"),
            "destination_mac": context.get("destination_mac"),
        }
        if "vid" in context:
            receive_interface_info["vid"] = context["vid"]
        return receive_interface_info

    def datagramReceived(self, datagram, addr):
        """Called by Twisted when a UDP datagram is received.

        Note: In the typical use case, the MAAS server will ignore packets
        coming into this method. We need to listen to the socket normally,
        however, so that the underlying network stack will send ICMP
        destination (port) unreachable replies to anyone trying to send us
        beacons. However, at other times, (such as while running the test
        commands), we *will* listen to the socket layer for beacons.
        """
        if self.process_incoming:
            context = {"source_ip": addr[0], "source_port": addr[1]}
            beacon_json = beacon_to_json(read_beacon_payload(datagram))
            beacon_json.update(context)
            self.beaconReceived(beacon_json)


class NetworksMonitoringLock(NamedLock):
    """Host scoped lock to ensure only one network monitoring service runs."""

    def __init__(self):
        super().__init__("networks-monitoring")


class SingleInstanceService(MultiService, metaclass=ABCMeta):
    """A service which can have only a single instance per machine.

    It uses a named filesystem lock to prevent more than one instance running
    on each host machine. This service attempts to acquire this lock on each
    loop, and then it holds the lock until the service stops.

    """

    # The service name. Subclasses must define this.
    SERVICE_NAME = None
    # The lock name. Subclasses must define this.
    LOCK_NAME = None
    # The interval at which the service action is run. Subclasses
    # must define it as a timedelta
    INTERVAL = None

    def __init__(self, clock=None):
        # Order is very important here. First we set the clock to the passed-in
        # reactor, so that unit tests can fake out the clock if necessary.
        # Then we call super(). The superclass will set up the structures
        # required to add parents to this service, which allows the remainder
        # of this method to succeed. (And do so without the side-effect of
        # executing calls that shouldn't be executed based on the desired
        # reactor.)
        self.clock = clock
        super().__init__()
        self._lock = NamedLock(self.LOCK_NAME)
        self._locked = False
        # setup the periodic service
        self._timer_service = TimerService(
            self.INTERVAL.total_seconds(), self._do_action
        )
        self._timer_service.setName(self.SERVICE_NAME)
        self._timer_service.clock = self.clock
        self._timer_service.setServiceParent(self)

    @abstractmethod
    def do_action(self):
        """The action to execute each interval. Subclasses must define this."""

    @property
    def is_responsible(self):
        """Return whether the service is responsible for running the action."""
        return self._locked

    def stopService(self):
        """Stop the service.

        Ensures that sole responsibility is released.
        """
        d = super().stopService()
        d.addBoth(callOut, self._release_sole_responsibility)
        return d

    @inlineCallbacks
    def _do_action(self):
        if not self.running:
            return

        if self._assume_sole_responsibility():
            yield self.do_action()

    def _assume_sole_responsibility(self):
        """Assuming sole responsibility for the service action.

        It does this by attempting to acquire a lock. If this service already
        holds the lock this is a no-op.

        Return True if it has responsibility, False otherwise.
        """
        if self._locked:
            return True

        try:
            self._lock.acquire()
        except self._lock.NotAvailable:
            return False
        else:
            maaslog.info(
                f"{self.LOCK_NAME}: "
                f"Process ID {os.getpid()} assumed responsibility."
            )
            self._locked = True
            return True

    def _release_sole_responsibility(self):
        """Releases sole responsibility for performing the service action.

        If this service is not currently responsible this is a no-op.
        """
        if not self._locked:
            return

        self._lock.release()
        self._locked = False


class NetworksMonitoringService(SingleInstanceService):
    """Service to monitor network interfaces for configuration changes."""

    SERVICE_NAME = "updateInterfaces"
    LOCK_NAME = "networks-monitoring"
    INTERVAL = timedelta(seconds=30)

    def __init__(
        self,
        clock=None,
        enable_monitoring=True,
        enable_beaconing=True,
    ):
        super().__init__(clock=clock)
        self.enable_monitoring = enable_monitoring
        self.enable_beaconing = enable_beaconing
        # The last successfully recorded interfaces.
        self._recorded = None
        self._monitored = frozenset()
        self._beaconing = frozenset()
        self._monitoring_state = {}
        self._monitoring_mdns = False
        self.beaconing_protocol = None

    @inlineCallbacks
    def do_action(self):
        """Update interfaces, catching and logging errors.

        This can be overridden by subclasses to conditionally update based on
        some external configuration.
        """
        interfaces = None
        try:
            interfaces = yield maybeDeferred(self.getInterfaces)
            yield self._updateInterfaces(interfaces)
        except BaseException as e:
            msg = (
                "Failed to update and/or record network interface "
                "configuration: %s; interfaces: %r" % (e, interfaces)
            )
            log.err(None, msg)

    def getInterfaces(self):
        """Get the current network interfaces configuration.

        This can be overridden by subclasses.
        """
        return deferToThread(get_all_interfaces_definition)

    @abstractmethod
    def getDiscoveryState(self):
        """Record the interfaces information.

        This MUST be overridden in subclasses.
        """

    @abstractmethod
    def getRefreshDetails(self, interfaces, hints=None):
        """Get the details for posting commissioning script output.

        Returns a 3-tuple of (maas_url, system_id, credentials).

        This MUST be overridden in subclasses.
        """

    @abstractmethod
    def reportNeighbours(self, neighbours):
        """Report on new or refreshed neighbours.

        This MUST be overridden in subclasses.
        """

    @abstractmethod
    def reportMDNSEntries(self, mdns):
        """Report on new or refreshed neighbours.

        This MUST be overridden in subclasses.
        """

    def reportBeacons(self, beacons):
        """Receives a report of an observed beacon packet."""
        for beacon in beacons:
            self.beaconing_protocol.beaconReceived(beacon)

    def stopService(self):
        """Stop the service.

        Ensures that sole responsibility for monitoring networks is released.
        """
        if self.is_responsible:
            # If we were monitoring neighbours on any interfaces, we need to
            # stop the monitoring services.
            self._configureNetworkDiscovery({})
            if self.beaconing_protocol is not None:
                self._configureBeaconing({})

        if self.beaconing_protocol is not None:
            self.beaconing_protocol.stopProtocol()
        return super().stopService()

    def _get_topology_hints(self):
        # serialize hints and remove empty values to make the payload
        # smaller
        return [
            {
                key: value
                for key, value in hint._asdict().items()
                if value is not None
            }
            for hint in self.beaconing_protocol.getAllTopologyHints()
        ]

    @inlineCallbacks
    def _updateInterfaces(self, interfaces):
        """Record `interfaces` if they've changed."""
        if interfaces != self._recorded:
            hints = None
            if self.enable_beaconing:
                self._configureBeaconing(interfaces)
                # Wait for beaconing to do its thing.
                yield pause(3.0)
                # Retry beacon soliciations, in case any packet loss occurred
                # the first time.
                self.beaconing_protocol.queueMulticastBeaconing(
                    solicitation=True
                )
                yield pause(3.0)
                hints = self._get_topology_hints()

            maas_url, system_id, credentials = yield self.getRefreshDetails()
            yield self._run_refresh(
                maas_url,
                system_id,
                credentials,
                interfaces,
                hints,
            )
            # Note: _interfacesRecorded() will reconfigure discovery after
            # recording the interfaces, so there is no need to call
            # _configureNetworkDiscovery() here.
            self._interfacesRecorded(interfaces)
        else:
            # Send out beacons unsolicited once every 30 seconds. (Use
            # solicitations so that replies will be received, that way peers
            # will reply and the hinting will be accurate.)
            if self.enable_beaconing:
                self.beaconing_protocol.queueMulticastBeaconing(
                    solicitation=True
                )
            # If the interfaces didn't change, we still need to poll for
            # monitoring state changes.
            yield maybeDeferred(self._configureNetworkDiscovery, interfaces)

    @inlineCallbacks
    def _run_refresh(
        self, maas_url, system_id, credentials, interfaces, hints
    ):
        yield deferToThread(
            refresh,
            system_id,
            credentials["consumer_key"],
            credentials["token_key"],
            credentials["token_secret"],
            maas_url,
            post_process_hook=functools.partial(
                self._annotate_commissioning, interfaces, hints
            ),
        )

    def _annotate_commissioning(
        self,
        interfaces,
        hints,
        script_name,
        combined_path,
        stdout_path,
        stderr_path,
    ):
        if script_name != COMMISSIONING_OUTPUT_NAME:
            return
        script_stdout = Path(stdout_path)
        with script_stdout.open() as fp:
            lxd_data = json.load(fp)
        lxd_data["network-extra"] = {
            "interfaces": interfaces,
            "monitored-interfaces": get_default_monitored_interfaces(
                interfaces
            ),
            "hints": hints,
        }
        with script_stdout.open("w") as fp:
            json.dump(lxd_data, fp, indent=4)
        Path(combined_path).write_text(
            script_stdout.read_text() + Path(stderr_path).read_text()
        )

    def _getInterfacesForBeaconing(self, interfaces: dict):
        """Return the interfaces which will be used for beaconing.

        :return: The set of interface names to run beaconing on.
        """
        # Don't beacon when running the test suite/dev env.
        # In addition, if we don't own the lock, we should not be beaconing.
        if is_dev_environment() or not self._locked or interfaces is None:
            return set()
        monitored_interfaces = {
            ifname
            for ifname, ifdata in interfaces.items()
            if ifdata["monitored"]
        }
        return monitored_interfaces

    def _getInterfacesForNeighbourDiscovery(
        self, interfaces: dict, monitoring_state: dict
    ):
        """Return the interfaces which will be used for neighbour discovery.

        :return: The set of interface names to run neighbour discovery on.
        """
        # Don't observe interfaces when running the test suite/dev env.
        # In addition, if we don't own the lock, we should not be monitoring
        # any interfaces.
        if is_dev_environment() or not self._locked or interfaces is None:
            return set()
        monitored_interfaces = {
            ifname
            for ifname in interfaces
            if (
                ifname in monitoring_state
                and monitoring_state[ifname].get("neighbour", False)
            )
        }
        return monitored_interfaces

    def _startNeighbourDiscovery(self, ifname):
        """Start neighbour discovery service on the specified interface."""
        service = NeighbourDiscoveryService(ifname, self.reportNeighbours)
        service.clock = self.clock
        service.setName("neighbour_discovery:" + ifname)
        service.setServiceParent(self)

    def _startBeaconing(self, ifname):
        """Start neighbour discovery service on the specified interface."""
        service = BeaconingService(ifname, self.reportBeacons)
        service.clock = self.clock
        service.setName("beaconing:" + ifname)
        service.setServiceParent(self)

    def _startMDNSDiscoveryService(self):
        """Start resolving mDNS entries on attached networks."""
        try:
            self.getServiceNamed("mdns_resolver")
        except KeyError:
            # This is an expected exception. (The call inside the `try`
            # is only necessary to ensure the service doesn't exist.)
            service = MDNSResolverService(self.reportMDNSEntries)
            service.clock = self.clock
            service.setName("mdns_resolver")
            service.setServiceParent(self)

    def _stopMDNSDiscoveryService(self):
        """Stop resolving mDNS entries on attached networks."""
        try:
            service = self.getServiceNamed("mdns_resolver")
        except KeyError:
            # Service doesn't exist, so no need to stop it.
            pass
        else:
            service.disownServiceParent()
            maaslog.info("Stopped mDNS resolver service.")

    def _startNeighbourDiscoveryServices(self, new_interfaces):
        """Start monitoring services for the specified set of interfaces."""
        for ifname in new_interfaces:
            # Sanity check to ensure the service isn't already started.
            try:
                self.getServiceNamed("neighbour_discovery:" + ifname)
            except KeyError:
                # This is an expected exception. (The call inside the `try`
                # is only necessary to ensure the service doesn't exist.)
                self._startNeighbourDiscovery(ifname)

    def _stopNeighbourDiscoveryServices(self, deleted_interfaces):
        """Stop monitoring services for the specified set of interfaces."""
        for ifname in deleted_interfaces:
            try:
                service = self.getServiceNamed("neighbour_discovery:" + ifname)
            except KeyError:
                # Service doesn't exist, so no need to stop it.
                pass
            else:
                service.disownServiceParent()
                maaslog.info(
                    "Stopped neighbour observation service for %s." % ifname
                )

    def _startBeaconingServices(self, new_interfaces):
        """Start monitoring services for the specified set of interfaces."""
        for ifname in new_interfaces:
            # Sanity check to ensure the service isn't already started.
            try:
                self.getServiceNamed("beaconing:" + ifname)
            except KeyError:
                # This is an expected exception. (The call inside the `try`
                # is only necessary to ensure the service doesn't exist.)
                self._startBeaconing(ifname)

    def _stopBeaconingServices(self, deleted_interfaces):
        """Stop monitoring services for the specified set of interfaces."""
        for ifname in deleted_interfaces:
            try:
                service = self.getServiceNamed("beaconing:" + ifname)
            except KeyError:
                # Service doesn't exist, so no need to stop it.
                pass
            else:
                service.disownServiceParent()
                maaslog.info("Stopped beaconing service for %s." % ifname)

    def _shouldMonitorMDNS(self, monitoring_state):
        # If any interface is configured for mDNS, we must start the monitoring
        # process. (You cannot select interfaces when using `avahi-browse`.)
        mdns_state = {
            monitoring_state[ifname].get("mdns", False)
            for ifname in monitoring_state.keys()
        }
        return True in mdns_state

    @inlineCallbacks
    def _configureNetworkDiscovery(self, interfaces):
        """Update the set of monitored interfaces.

        Calculates the difference between the interfaces that are currently
        being monitored and the new list of interfaces enabled for discovery.

        Starts services for any new interfaces, and stops services for any
        deleted interface.

        Updates `self._monitored` with the current set of interfaces being
        monitored.
        """
        if interfaces is None:
            # This is a no-op if we don't have any interfaces to monitor yet.
            # (An empty dictionary tells us not to monitor any interfaces.)
            return
        # Don't bother calling the region if the interface dictionary
        # hasn't yet been populated, or was intentionally set to nothing.
        if len(interfaces) > 0:
            monitoring_state = yield maybeDeferred(self.getDiscoveryState)
        else:
            monitoring_state = {}
        # If the monitoring state has changed, we need to potentially start
        # or stop some services.
        if self._monitoring_state != monitoring_state:
            log.msg("New interface monitoring state: %r" % monitoring_state)
            self._configureNeighbourDiscovery(interfaces, monitoring_state)
            self._configureMDNS(monitoring_state)
            self._monitoring_state = monitoring_state

    def _configureMDNS(self, monitoring_state):
        should_monitor_mdns = self._shouldMonitorMDNS(monitoring_state)
        if not self._monitoring_mdns and should_monitor_mdns:
            # We weren't currently monitoring any interfaces, but we have been
            # requested to monitor at least one.
            self._startMDNSDiscoveryService()
            self._monitoring_mdns = True
        elif self._monitoring_mdns and not should_monitor_mdns:
            # We are currently monitoring at least one interface, but we have
            # been requested to stop monitoring them all.
            self._stopMDNSDiscoveryService()
            self._monitoring_mdns = False
        else:
            # No state change. We either still AREN'T monitoring any
            # interfaces, or we still ARE monitoring them. (Either way, it
            # doesn't matter for mDNS discovery purposes.)
            pass

    def _configureBeaconing(self, interfaces):
        beaconing_interfaces = self._getInterfacesForBeaconing(interfaces)
        # Calculate the difference between the sets. We need to know which
        # interfaces were added and deleted (with respect to the interfaces we
        # were already beaconing on).
        new_interfaces = beaconing_interfaces.difference(self._beaconing)
        deleted_interfaces = self._beaconing.difference(beaconing_interfaces)
        if len(new_interfaces) > 0:
            log.msg("Starting beaconing for interfaces: %r" % new_interfaces)
            self._startBeaconingServices(new_interfaces)
        if len(deleted_interfaces) > 0:
            log.msg(
                "Stopping beaconing for interfaces: %r" % deleted_interfaces
            )
            self._stopBeaconingServices(deleted_interfaces)
        self._beaconing = beaconing_interfaces
        if self.beaconing_protocol is None:
            self.beaconing_protocol = BeaconingSocketProtocol(
                self.clock, interfaces=interfaces
            )
        else:
            self.beaconing_protocol.updateInterfaces(interfaces)
        # If the interfaces have changed, perform beaconing again.
        # An empty dictionary will be passed in when the service stops, so
        # don't bother sending out beacons we won't reply to.
        if len(interfaces) > 0:
            self.beaconing_protocol.queueMulticastBeaconing(solicitation=True)

    def _configureNeighbourDiscovery(self, interfaces, monitoring_state):
        monitored_interfaces = self._getInterfacesForNeighbourDiscovery(
            interfaces, monitoring_state
        )
        # Calculate the difference between the sets. We need to know which
        # interfaces were added and deleted (with respect to the interfaces we
        # were already monitoring).
        new_interfaces = monitored_interfaces.difference(self._monitored)
        deleted_interfaces = self._monitored.difference(monitored_interfaces)
        if len(new_interfaces) > 0:
            log.msg(
                "Starting neighbour discovery for interfaces: %r"
                % new_interfaces
            )
            self._startNeighbourDiscoveryServices(new_interfaces)
        if len(deleted_interfaces) > 0:
            log.msg(
                "Stopping neighbour discovery for interfaces: %r"
                % deleted_interfaces
            )
            self._stopNeighbourDiscoveryServices(deleted_interfaces)
        self._monitored = monitored_interfaces

    def _interfacesRecorded(self, interfaces):
        """The given `interfaces` were recorded successfully."""
        self._recorded = interfaces
        if self.enable_monitoring:
            self._configureNetworkDiscovery(interfaces)
