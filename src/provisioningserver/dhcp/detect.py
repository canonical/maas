# Copyright 2013-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Utilities and helpers to help discover DHCP servers on your network."""

from contextlib import contextmanager
import errno
import fcntl
from os import strerror
from random import randint
import socket
import struct
import time
from typing import List, Optional

import attr
from netaddr import IPAddress
from twisted.internet import reactor
from twisted.internet.defer import (
    CancelledError,
    Deferred,
    DeferredList,
    FirstError,
    inlineCallbacks,
)
from twisted.internet.interfaces import IReactorThreads
from twisted.internet.task import deferLater
from twisted.internet.threads import blockingCallFromThread, deferToThread
from twisted.python.failure import Failure

from provisioningserver.logger import get_maas_logger, LegacyLogger
from provisioningserver.utils.dhcp import DHCP

maaslog = get_maas_logger("dhcp.detect")
log = LegacyLogger()


def make_dhcp_transaction_id() -> bytes:
    """Generate and return a random DHCP transaction identifier."""
    transaction_id = b""
    for _ in range(4):
        transaction_id += struct.pack(b"!B", randint(0, 255))
    return transaction_id


class DHCPDiscoverPacket:
    """A representation of a DHCP_DISCOVER packet.

    :param mac: The MAC address to which the dhcp server should respond.
        Normally this is the MAC of the interface you're using to send the
        request.
    """

    def __init__(
        self, mac: str = None, transaction_id: bytes = None, seconds: int = 0
    ):
        super().__init__()
        self.mac_bytes = None
        self.mac_str = None
        self.seconds = seconds
        if transaction_id is None:
            self.transaction_id = make_dhcp_transaction_id()
        else:
            self.transaction_id = transaction_id
        if mac is not None:
            self.set_mac(mac)

    def __hash__(self):
        # Needed for unit tests.
        return hash((self.mac_bytes, self.seconds, self.transaction_id))

    def __eq__(self, other):
        # Needed for unit tests.
        return (self.mac_bytes, self.seconds, self.transaction_id) == (
            other.mac_bytes,
            other.seconds,
            other.transaction_id,
        )

    @staticmethod
    def mac_string_to_bytes(mac: str) -> bytes:
        """Convert a string MAC address to 6 hex octets.

        :param mac: A MAC address in the format AA:BB:CC:DD:EE:FF
        :return: a byte string of length 6
        """
        mac_bytes = b""
        for pair in mac.split(":"):
            hex_octet = int(pair, 16)
            mac_bytes += struct.pack(b"!B", hex_octet)
        return mac_bytes

    def set_mac(self, mac: str) -> None:
        """Sets the MAC address used for the client hardware address, and
        client unique identifier option.
        """
        self.mac_bytes = self.mac_string_to_bytes(mac)
        self.mac_str = mac

    @property
    def client_uid_option(self) -> bytes:
        """Returns a `bytes` object representing the client UID.

        The `set_mac()` method must have been called prior to using this.
        """
        # Option: (6=61,l=~23) Client Unique Identifier
        # Make our unique identifier a little more unique by adding "MAAS-",
        # so it will look like "\x00MAAS-00:00:00:00:00:00\x00"
        # See https://tools.ietf.org/html/rfc2132#section-9.14 for details.
        client_id = b"\x00MAAS-" + self.mac_str.encode("ascii")
        client_id_len = len(client_id).to_bytes(1, "big")
        return b"\x3d" + client_id_len + client_id

    @property
    def packet(self) -> bytes:
        """Builds and returns the packet based on specified MAC and seconds."""
        return (
            # Message type: Boot Request (1)
            b"\x01"
            # Hardware type: Ethernet
            b"\x01"
            # Hardware address length: 6
            b"\x06"
            # Hops: 0
            b"\x00" + self.transaction_id + self.seconds.to_bytes(2, "big") +
            # Flags: the most significant bit is the broadcast bit.
            #     0x8000 means "force the server to use broadcast".
            #     0x0000 means "it's okay to unicast replies".
            # We will miss packets from some DHCP servers if we don't prefer
            # unicast. (For example, a DD-WRT router was observed sending to
            # the broadcast address from a link-local IPv4 address, which was
            # rejected by the IP stack before the socket could recv() it.)
            b"\x00\x00"
            # Client IP address: 0.0.0.0
            b"\x00\x00\x00\x00"
            # Your (client) IP address: 0.0.0.0
            b"\x00\x00\x00\x00"
            # Next server IP address: 0.0.0.0
            b"\x00\x00\x00\x00"
            # Relay agent IP address: 0.0.0.0
            b"\x00\x00\x00\x00" +
            # Client hardware address
            self.mac_bytes
            +
            # Client hardware address padding: 00000000000000000000
            b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
            +
            # Server host name not given
            (b"\x00" * 67)
            +
            # Boot file name not given
            (b"\x00" * 125)
            +
            # Magic cookie: DHCP
            b"\x63\x82\x53\x63"
            # Option: (t=53,l=1) DHCP Message Type = DHCP Discover
            b"\x35\x01\x01"
            + self.client_uid_option
            +
            # Option: (t=55,l=3) Parameter Request List
            b"\x37\x03\x03\x01\x06"
            +
            # End Option
            b"\xff"
        )


# UDP ports for the BOOTP protocol.  Used for discovery requests.
BOOTP_SERVER_PORT = 67
BOOTP_CLIENT_PORT = 68

# ioctl request for requesting IP address.
SIOCGIFADDR = 0x8915

# ioctl request for requesting hardware (MAC) address.
SIOCGIFHWADDR = 0x8927


def get_interface_mac(sock: socket.socket, ifname: str) -> str:
    """Obtain a network interface's MAC address, as a string."""
    ifreq = struct.pack(b"256s", ifname.encode("utf-8")[:15])
    try:
        info = fcntl.ioctl(sock.fileno(), SIOCGIFHWADDR, ifreq)
    except OSError as e:
        if e.errno is not None and e.errno == errno.ENODEV:
            raise InterfaceNotFound("Interface not found: '%s'." % ifname)  # noqa: B904
        else:
            raise MACAddressNotAvailable(  # noqa: B904
                "Failed to get MAC address for '%s': %s."
                % (ifname, strerror(e.errno))
            )
    else:
        # Of course we're sure these are the correct indexes into the `ifreq`.
        # Also, your lack of faith is disturbing.
        mac = "".join("%02x:" % char for char in info[18:24])[:-1]
    return mac


def get_interface_ip(sock: socket.socket, ifname: str) -> str:
    """Obtain an IP address for a network interface, as a string."""
    ifreq_tuple = (ifname.encode("utf-8")[:15], socket.AF_INET, b"\x00" * 14)
    ifreq = struct.pack(b"16sH14s", *ifreq_tuple)
    try:
        info = fcntl.ioctl(sock, SIOCGIFADDR, ifreq)
    except OSError as e:
        if e.errno == errno.ENODEV:
            raise InterfaceNotFound("Interface not found: '%s'." % ifname)  # noqa: B904
        elif e.errno == errno.EADDRNOTAVAIL:
            raise IPAddressNotAvailable(  # noqa: B904
                "No IP address found on interface '%s'." % ifname
            )
        else:
            raise IPAddressNotAvailable(  # noqa: B904
                "Failed to get IP address for '%s': %s."
                % (ifname, strerror(e.errno))
            )
    else:
        (  # Parse the `struct ifreq` that comes back from the ioctl() call.
            #     16x --> char ifr_name[IFNAMSIZ];
            # ... next is a union of structures; we're interested in the
            # `sockaddr_in` that is returned from this particular ioctl().
            #     2x  --> short sin_family;
            #     2x  --> unsigned short sin_port;
            #     4s  --> struct in_addr sin_addr;
            #     8x  --> char sin_zero[8];
            addr,
        ) = struct.unpack(b"16x2x2x4s8x", info)
        ip = socket.inet_ntoa(addr)
    return ip


@contextmanager
def udp_socket():
    """Open, and later close, a UDP socket."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    # We're going to bind to the BOOTP/DHCP client socket, where dhclient may
    # also be listening, even if it's operating on a different interface!
    # The SO_REUSEADDR option makes this possible.
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        yield sock
    finally:
        sock.close()


class DHCPProbeException(Exception):
    """Class of known-possible exceptions during DHCP probing.

    These exceptions are logged without including the traceback.
    """


class IPAddressNotAvailable(DHCPProbeException):
    """Raised when an interface's IP address could not be determined."""


class MACAddressNotAvailable(DHCPProbeException):
    """Raised when an interface's MAC address could not be determined."""


class InterfaceNotFound(DHCPProbeException):
    """Raised when an interface could not be found."""


def send_dhcp_request_packet(request: DHCPDiscoverPacket, ifname: str) -> None:
    """Sends out the specified DHCP discover packet to the given interface.

    Optionally takes a `retry_call` to cancel if a fatal error occurs before
    the first packet can be sent, such as inability to get a source IP
    address.
    """
    with udp_socket() as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        mac = get_interface_mac(sock, ifname)
        request.set_mac(mac)
        bind_address = get_interface_ip(sock, ifname)
        sock.bind((bind_address, BOOTP_CLIENT_PORT))
        sock.sendto(request.packet, ("<broadcast>", BOOTP_SERVER_PORT))


# Packets will be sent at the following intervals (in seconds).
# The length of `DHCP_REQUEST_TIMING` indicates the number of packets
# that will be sent. The values should get progressively larger, to mimic
# the exponential back-off retry behavior of a real DHCP client.
DHCP_REQUEST_TIMING = (0, 2, 4, 8)

# Wait `REPLY_TIMEOUT` seconds to receive responses.
# This value should be a little larger than the largest value in the
# `DHCP_REQUEST_TIMING` tuple, to account for network and server delays.
REPLY_TIMEOUT = 10

# How long we should wait each iteration before waking up and checking if the
# timeout has elapsed.
SOCKET_TIMEOUT = 0.5


class DHCPRequestMonitor:
    def __init__(self, ifname: str, clock: IReactorThreads = None):
        if clock is None:
            clock = reactor
        self.clock = clock  # type: IReactorThreads
        self.ifname = ifname  # type: str
        self.servers = None  # type: set
        self.dhcpRequestsDeferredList = None  # type: DeferredList
        self.deferredDHCPRequests = []  # type: List[Deferred]
        self.transaction_id = make_dhcp_transaction_id()  # type: bytes

    def send_requests_and_await_replies(self):
        """Sends out DHCP requests and waits for their replies.

        This method is intended to run under `deferToThread()`.

        Calls the reactor using `blockingCallFromThread` to queue the request
        packets.

        Blocks for ~10 seconds while checking for DHCP offers.

        :returns: `set` of `DHCPServer` objects.
        """
        # Since deferToThread() might be delayed until the next thread is
        # available, it's better to kick off the DHCP requests from the
        # spawned thread rather than hoping the thread starts running after
        # we kick off the requests.
        blockingCallFromThread(self.clock, self.deferDHCPRequests)
        servers = set()
        # Convert the transaction_id to an integer so we can test it against
        # what the parsed DHCP packet will return.
        xid = int.from_bytes(self.transaction_id, byteorder="big")
        with udp_socket() as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            # Note: the empty string is the equivalent of INADDR_ANY.
            sock.bind(("", BOOTP_CLIENT_PORT))
            # The timeout has to be relatively small, since we wake up every
            # timeout interval to check the elapsed time.
            sock.settimeout(0.5)
            runtime = 0
            # Use a monotonic clock to ensure leaping backward in time won't
            # cause an infinite loop.
            start_time = time.monotonic()
            while runtime < REPLY_TIMEOUT:
                try:
                    # Use recvfrom() to check the source IP for the request.
                    # It could be interesting in cases where DHCP relay is in
                    # use.
                    data, (address, port) = sock.recvfrom(2048)
                except socket.timeout:
                    continue
                else:
                    offer = DHCP(data)
                    if not offer.valid:
                        log.info(
                            "Invalid DHCP response received from {address} "
                            "on '{ifname}': {reason}",
                            address=address,
                            ifname=self.ifname,
                            reason=offer.invalid_reason,
                        )
                    elif offer.packet.xid == xid:
                        # Offer matches our transaction ID, so check if it has
                        # a Server Identifier option.
                        server = offer.server_identifier
                        if server is not None:
                            servers.add(DHCPServer(server, address))
                finally:
                    runtime = time.monotonic() - start_time
        return servers

    @staticmethod
    def cancelAll(deferreds: List[Deferred]):
        for deferred in deferreds:
            deferred.cancel()

    def deferredDHCPRequestErrback(
        self, failure: Failure
    ) -> Optional[Failure]:
        if failure.check(FirstError):
            # If an error occurred, cancel any other pending requests.
            # (The error is likely to occur for those requests, too.)
            # Unfortunately we can't cancel using the DeferredList, since
            # the DeferredList considers itself "called" the moment the first
            # errback is invoked.
            self.cancelAll(self.deferredDHCPRequests)
            # Suppress further error handling. The original Deferred's errback
            # has already been called.
            return None
        elif failure.check(DHCPProbeException):
            log.msg("DHCP probe failed. %s" % failure.getErrorMessage())
        elif failure.check(CancelledError):
            # Intentionally cancelled; no need to spam the log.
            pass
        else:
            log.err(
                failure,
                "DHCP probe on '%s' failed with an unknown error."
                % (self.ifname),
            )
        # Make sure the error is propagated to the DeferredList.
        # We need this so that the DeferredList knows to call us with
        # FirstError, which is our indicator to cancel the remaining calls.
        # (It's set to consumeErrors, so it won't spam the log.)
        return failure

    def deferDHCPRequests(self) -> None:
        """Queues some DHCP requests to fire off later.

        Delays calls slightly so we have a chance to open a listen socket.

        Uses the `clock`, `ifname`, and `transaction_id` ivars.

        Stores a `DeferredList` of periodic DHCP requests calls in the
        `dhcpRequestsDeferredList` ivar, and the list of `Deferred` objects in
        the `deferredDHCPRequests` ivar.
        """
        self.deferredDHCPRequests = []
        for seconds in DHCP_REQUEST_TIMING:
            packet = DHCPDiscoverPacket(
                transaction_id=self.transaction_id, seconds=seconds
            )
            # Wait 0.1 seconds before sending the request, so we have a chance
            # to open a listen socket.
            seconds += 0.1
            deferred = deferLater(
                self.clock,
                seconds,
                send_dhcp_request_packet,
                packet,
                self.ifname,
            )
            deferred.addErrback(self.deferredDHCPRequestErrback)
            self.deferredDHCPRequests.append(deferred)
        # Use fireOnOneErrback so that we know to cancel the remaining attempts
        # to send requests if one of them fails.
        self.dhcpRequestsDeferredList = DeferredList(
            self.deferredDHCPRequests,
            fireOnOneErrback=True,
            consumeErrors=True,
        )
        self.dhcpRequestsDeferredList.addErrback(
            self.deferredDHCPRequestErrback
        )

    @inlineCallbacks
    def run(self) -> Deferred:
        """Queues DHCP requests to be sent, then waits (in a separate thread)
        for replies.

        Requests will be sent using an exponential back-off algorithm, to mimic
        a real DHCP client. But we'll just pretend we didn't see any of the
        replies, and hope for more servers to respond.

        The set of `DHCPServer`s that responded to the request(s) is stored
        in the `servers` ivar, which in turn makes the `dhcp_servers` and
        `dhcp_addresses` properties useful.
        """
        servers = yield deferToThread(self.send_requests_and_await_replies)
        if len(servers) > 0:
            log.info(
                "External DHCP server(s) discovered on interface '{ifname}': "
                "{servers}",
                ifname=self.ifname,
                servers=", ".join(
                    str(server) for server in sorted(list(servers))
                ),
            )
        self.servers = servers

    @property
    def dhcp_servers(self):
        return {str(server.server) for server in self.servers}

    @property
    def dhcp_addresses(self):
        return {str(server.address) for server in self.servers}


@attr.s(hash=True)
class DHCPServer:
    server = attr.ib(converter=IPAddress)
    address = attr.ib(converter=IPAddress)

    def __str__(self):
        """Returns either a longer format string (if the address we received
        the packet from is different from the DHCP server address specified in
        the packet) or a single IP address (if the address we received the
        packet from and the server address are the same).
        """
        if self.server == self.address:
            return str(self.server)
        return f"{self.server} (via {self.address})"


@inlineCallbacks
def probe_interface(interface):
    """Look for a DHCP server on the network.

    This must be run with provileges to broadcast from the BOOTP port, which
    typically requires root.  It may fail to bind to that port if a DHCP client
    is running on that same interface.

    :param interface: Network interface name, e.g. "eth0", attached to the
        network you wish to probe.
    :return: Set of discovered DHCP servers.
    """
    dhcp_request_monitor = DHCPRequestMonitor(interface)
    yield dhcp_request_monitor.run()
    # The caller expects a set of addresses in unicode format.
    # XXX We might want to consider using the address we got from
    # recvfrom(), since that is likely the address relaying to this
    # interface. (Those are stored in the `dchp_addresses` ivar.)
    # Further investigation required.
    return dhcp_request_monitor.dhcp_servers
