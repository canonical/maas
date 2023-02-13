# Copyright 2013-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for dhcp/detect.py"""


import errno
import random
import socket
from unittest import mock
from unittest.mock import call

from testtools import ExpectedException
from twisted.internet import reactor
from twisted.internet.defer import (
    CancelledError,
    DeferredList,
    inlineCallbacks,
)
from twisted.internet.task import Clock, deferLater
from twisted.python.failure import Failure

from maastesting.factory import factory
from maastesting.matchers import DocTestMatches, HasLength, MockCallsMatch
from maastesting.runtest import MAASTwistedRunTest
from maastesting.testcase import MAASTestCase
from maastesting.twisted import TwistedLoggerFixture
import provisioningserver.dhcp.detect as detect_module
from provisioningserver.dhcp.detect import (
    BOOTP_CLIENT_PORT,
    BOOTP_SERVER_PORT,
    DHCP_REQUEST_TIMING,
    DHCPDiscoverPacket,
    DHCPProbeException,
    DHCPRequestMonitor,
    DHCPServer,
    get_interface_ip,
    get_interface_mac,
    InterfaceNotFound,
    IPAddressNotAvailable,
    MACAddressNotAvailable,
    make_dhcp_transaction_id,
    probe_interface,
    send_dhcp_request_packet,
    udp_socket,
)


class TestMakeDHCPTransactionID(MAASTestCase):
    def test_produces_well_formed_id(self):
        # The DHCP transaction ID should be 4 bytes long.
        transaction_id = make_dhcp_transaction_id()
        self.assertIsInstance(transaction_id, bytes)
        self.assertEqual(4, len(transaction_id))

    def test_randomises(self):
        self.assertNotEqual(
            make_dhcp_transaction_id(), make_dhcp_transaction_id()
        )


class TestDHCPDiscoverPacket(MAASTestCase):
    def test_init_sets_transaction_id(self):
        transaction_id = make_dhcp_transaction_id()
        self.patch(
            detect_module, "make_dhcp_transaction_id"
        ).return_value = transaction_id
        discover = DHCPDiscoverPacket(factory.make_mac_address())
        self.assertEqual(transaction_id, discover.transaction_id)

    def test_init_sets_mac_bytes(self):
        mac = factory.make_mac_address()
        discover = DHCPDiscoverPacket(mac)
        self.assertEqual(discover.mac_string_to_bytes(mac), discover.mac_bytes)

    def test_packet_property_after_init_with_mac_and_no_transaction_id(self):
        discover = DHCPDiscoverPacket(factory.make_mac_address())
        self.assertIsNotNone(discover.packet)

    def test_converts_byte_string_to_bytes(self):
        discover = DHCPDiscoverPacket
        expected = b"\x01\x22\x33\x99\xaa\xff"
        input = "01:22:33:99:aa:ff"
        self.assertEqual(expected, discover.mac_string_to_bytes(input))

    def test_builds_packet(self):
        mac = factory.make_mac_address()
        seconds = random.randint(0, 1024)
        xid = factory.make_bytes(4)
        discover = DHCPDiscoverPacket(
            transaction_id=xid, mac=mac, seconds=seconds
        )
        seconds_bytes = seconds.to_bytes(2, "big")
        expected = (
            b"\x01\x01\x06\x00"
            + xid
            + seconds_bytes
            + b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
            + b"\x00\x00\x00\x00\x00\x00"
            + discover.mac_bytes
            + b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
            + b"\x00" * 67
            + b"\x00" * 125
            + b"\x63\x82\x53\x63\x35\x01\x01"
            + discover.client_uid_option
            + b"\x37\x03\x03\x01\x06\xff"
        )
        self.assertEqual(expected, discover.packet)


class TestGetInterfaceMAC(MAASTestCase):
    """Tests for `get_interface_mac`."""

    def test_loopback_has_zero_mac(self):
        # It's a lame test, but what other network interfaces can we reliably
        # test this on?
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.assertEqual("00:00:00:00:00:00", get_interface_mac(sock, "lo"))

    def test_invalid_interface_raises_interfacenotfound(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        with ExpectedException(InterfaceNotFound):
            get_interface_mac(sock, factory.make_unicode_string(size=15))

    def test_no_mac_raises_macaddressnotavailable(self):
        mock_ioerror = IOError()
        mock_ioerror.errno = errno.EOPNOTSUPP
        self.patch(detect_module.fcntl, "ioctl").side_effect = mock_ioerror
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # Drive-by test for the strerror() call.
        with ExpectedException(MACAddressNotAvailable, ".*not supported.*"):
            get_interface_mac(sock, "lo")


class TestGetInterfaceIP(MAASTestCase):
    """Tests for `get_interface_ip`."""

    def test_loopback_has_localhost_address(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.assertEqual("127.0.0.1", get_interface_ip(sock, "lo"))

    def test_invalid_interface_raises_interfacenotfound(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        with ExpectedException(detect_module.InterfaceNotFound):
            get_interface_ip(sock, factory.make_unicode_string(size=15))

    def test_no_ip_raises_ipaddressnotavailable(self):
        mock_ioerror = IOError()
        mock_ioerror.errno = errno.EADDRNOTAVAIL
        self.patch(detect_module.fcntl, "ioctl").side_effect = mock_ioerror
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        with ExpectedException(IPAddressNotAvailable, ".*No IP address.*"):
            get_interface_ip(sock, "lo")

    def test_unknown_errno_ip_raises_ipaddressnotavailable(self):
        mock_ioerror = IOError()
        mock_ioerror.errno = errno.EACCES
        self.patch(detect_module.fcntl, "ioctl").side_effect = mock_ioerror
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # Drive-by test for the strerror() call.
        with ExpectedException(
            IPAddressNotAvailable, "Failed.*Permission denied."
        ):
            get_interface_ip(sock, "lo")


def patch_socket(testcase):
    """Patch `socket.socket` to return a mock."""
    sock = mock.MagicMock()
    testcase.patch(
        detect_module.socket, "socket", mock.MagicMock(return_value=sock)
    )
    return sock


class TestUDPSocket(MAASTestCase):
    """Tests for `udp_socket`."""

    def test_yields_open_socket(self):
        patch_socket(self)
        with udp_socket() as sock:
            socket_calls = list(socket.socket.mock_calls)
            close_calls = list(sock.close.mock_calls)
        self.assertEqual(
            [mock.call(socket.AF_INET, socket.SOCK_DGRAM)], socket_calls
        )
        self.assertEqual([], close_calls)

    def test_closes_socket_on_exit(self):
        patch_socket(self)
        with udp_socket() as sock:
            pass
        self.assertEqual([mock.call()], sock.close.mock_calls)

    def test_sets_reuseaddr(self):
        patch_socket(self)
        with udp_socket() as sock:
            pass
        self.assertEqual(
            [mock.call(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)],
            sock.setsockopt.mock_calls,
        )


class TestSendDHCPRequestPacket(MAASTestCase):
    def test_sends_expected_packet(self):
        mock_socket = patch_socket(self)
        mock_socket.bind = mock.MagicMock()
        mock_socket.sendto = mock.MagicMock()
        self.patch(detect_module.get_interface_ip).return_value = "127.0.0.1"
        self.patch(
            detect_module.get_interface_mac
        ).return_value = "00:00:00:00:00:00"
        request = DHCPDiscoverPacket()
        send_dhcp_request_packet(request, "lo")
        self.assertThat(
            mock_socket.bind,
            MockCallsMatch(call(("127.0.0.1", BOOTP_CLIENT_PORT))),
        )
        self.assertThat(
            mock_socket.sendto,
            MockCallsMatch(
                call(request.packet, ("<broadcast>", BOOTP_SERVER_PORT))
            ),
        )


def make_Failure(exception_type, *args, **kwargs):
    try:
        raise exception_type(*args, **kwargs)
    except Exception:
        return Failure()


class TestDHCPRequestMonitor(MAASTestCase):
    run_tests_with = MAASTwistedRunTest.make_factory(debug=False, timeout=5)

    def test_send_requests_and_await_replies(self):
        # This test is a bit large because it covers the entire functionality
        # of the `send_requests_and_await_replies()` method. (It could be
        # split apart into multiple tests, but the large amount of setup work
        # and interdependencies makes that a maintenance burden.)
        mock_socket = patch_socket(self)
        mock_socket.bind = mock.MagicMock()
        mock_socket.recvfrom = mock.MagicMock()
        mock_socket.setsockopt = mock.MagicMock()
        mock_socket.settimeout = mock.MagicMock()
        # Pretend we were successful at deferring the DHCP requests.
        self.patch_autospec(detect_module, "blockingCallFromThread")
        # This method normally blocks for ~10 seconds, so take control of the
        # monotonic clock and make sure the last call to `recvfrom()` happens
        # just as we hit the reply timeout.
        mock_time_monotonic = self.patch(detect_module.time.monotonic)
        mock_time_monotonic.side_effect = (
            # Start time (before loop starts).
            10,
            # First reply (truncated packet).
            11,
            # Second reply (not a match to our transaction).
            12,
            # Third reply (Matching reply with server identifier option).
            13,
            # First socket timeout (need to make sure the loop continues).
            14,
            # Second socket timeout (hey, we're done!).
            10 + detect_module.REPLY_TIMEOUT,
        )
        mock_xid = factory.make_bytes(4)
        valid_dhcp_reply = factory.make_dhcp_packet(
            transaction_id=mock_xid,
            include_server_identifier=True,
            server_ip="127.1.1.1",
        )
        mock_get_xid = self.patch(detect_module.make_dhcp_transaction_id)
        mock_get_xid.return_value = mock_xid
        # Valid DHCP packet, but not a match because it doesn't have a
        # Server Identifier option.
        valid_non_match = DHCPDiscoverPacket(
            mac="01:02:03:04:05:06", transaction_id=mock_xid
        ).packet
        mock_socket.recvfrom.side_effect = (
            # Truncated packet, to test logging.
            (b"", ("127.0.0.1", BOOTP_SERVER_PORT)),
            (valid_non_match, ("127.0.0.2", BOOTP_SERVER_PORT)),
            (valid_dhcp_reply, ("127.0.0.3", BOOTP_SERVER_PORT)),
            socket.timeout,
            socket.timeout,
        )
        logger = self.useFixture(TwistedLoggerFixture())
        monitor = DHCPRequestMonitor("lo", Clock())
        result = monitor.send_requests_and_await_replies()
        self.assertThat(
            mock_socket.setsockopt,
            MockCallsMatch(
                call(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1),
                call(socket.SOL_SOCKET, socket.SO_BROADCAST, 1),
            ),
        )
        self.assertThat(mock_socket.bind, MockCallsMatch(call(("", 68))))
        self.assertThat(
            mock_socket.settimeout,
            MockCallsMatch(call(detect_module.SOCKET_TIMEOUT)),
        )
        self.assertThat(
            mock_socket.recvfrom,
            MockCallsMatch(
                call(2048), call(2048), call(2048), call(2048), call(2048)
            ),
        )
        # One of the response packets was truncated.
        self.assertThat(
            logger.output,
            DocTestMatches("Invalid DHCP response...Truncated..."),
        )
        self.assertThat(result, HasLength(1))
        # Ensure we record the fact that the reply packet came from a different
        # IP address than the server claimed to be.
        self.assertIn(DHCPServer("127.1.1.1", "127.0.0.3"), result)

    @inlineCallbacks
    def test_cancelAll(self):
        self.errbacks_called = 0

        def mock_errback(result: Failure):
            self.assertTrue(result.check(CancelledError))
            self.errbacks_called += 1

        a = deferLater(reactor, 6, lambda: "a")
        b = deferLater(reactor, 6, lambda: "b")
        a.addBoth(mock_errback)
        b.addBoth(mock_errback)
        deferreds = [a, b]
        DHCPRequestMonitor.cancelAll(deferreds)
        deferredList = DeferredList(deferreds)
        yield deferredList
        self.assertEqual(2, self.errbacks_called)

    @inlineCallbacks
    def test_deferredDHCPRequestErrback_cancels_all_on_FirstError(self):
        mock_cancelAll = self.patch(DHCPRequestMonitor, "cancelAll")

        def raise_ioerror():
            raise OSError()

        a = deferLater(reactor, 0.0, raise_ioerror)
        b = deferLater(reactor, 6, lambda: "b")
        monitor = DHCPRequestMonitor("lo")
        monitor.deferredDHCPRequests = [a, b]
        deferredList = DeferredList(
            monitor.deferredDHCPRequests,
            consumeErrors=True,
            fireOnOneErrback=True,
        )
        deferredList.addErrback(monitor.deferredDHCPRequestErrback)
        yield deferredList
        # Still have one call left in the reactor, since we mocked cancelAll().
        b.cancel()
        self.assertThat(mock_cancelAll, MockCallsMatch(call([a, b])))

    def test_deferredDHCPRequestErrback_logs_known_exceptions(self):
        logger = self.useFixture(TwistedLoggerFixture())
        monitor = DHCPRequestMonitor("lo")
        error = factory.make_string()
        monitor.deferredDHCPRequestErrback(
            make_Failure(DHCPProbeException, error)
        )
        self.assertThat(
            logger.output, DocTestMatches("DHCP probe failed. %s" % error)
        )

    def test_deferredDHCPRequestErrback_logs_unknown_exceptions(self):
        logger = self.useFixture(TwistedLoggerFixture())
        monitor = DHCPRequestMonitor("lo")
        error = factory.make_string()
        monitor.deferredDHCPRequestErrback(make_Failure(IOError, error))
        self.assertThat(
            logger.output,
            DocTestMatches("...unknown error...Traceback...%s" % error),
        )

    def test_deferredDHCPRequestErrback_ignores_cancelled(self):
        logger = self.useFixture(TwistedLoggerFixture())
        monitor = DHCPRequestMonitor("lo")
        error = factory.make_string()
        monitor.deferredDHCPRequestErrback(make_Failure(CancelledError, error))
        self.assertThat(logger.output, DocTestMatches(""))

    def test_deferDHCPRequests(self):
        clock = Clock()
        monitor = DHCPRequestMonitor("lo", clock)
        mock_addErrback = mock.MagicMock()
        mock_deferredListResult = mock.MagicMock()
        mock_deferLater = self.patch(detect_module, "deferLater")
        mock_deferLater.return_value = mock.MagicMock()
        mock_deferLater.return_value.addErrback = mock_addErrback
        mock_DeferredList = self.patch(detect_module, "DeferredList")
        mock_DeferredList.return_value = mock_deferredListResult
        mock_deferredListResult.addErrback = mock_addErrback
        expected_calls = [
            call(
                clock,
                seconds + 0.1,
                send_dhcp_request_packet,
                DHCPDiscoverPacket(
                    transaction_id=monitor.transaction_id, seconds=seconds
                ),
                "lo",
            )
            for seconds in DHCP_REQUEST_TIMING
        ]
        monitor.deferDHCPRequests()
        self.assertThat(mock_deferLater, MockCallsMatch(*expected_calls))
        self.assertThat(
            mock_DeferredList,
            MockCallsMatch(
                call(
                    monitor.deferredDHCPRequests,
                    fireOnOneErrback=True,
                    consumeErrors=True,
                )
            ),
        )
        # Expect addErrback to be called both on each individual Deferred, plus
        # one more time on the DeferredList.
        expected_errback_calls = [
            call(monitor.deferredDHCPRequestErrback)
            for _ in range(len(DHCP_REQUEST_TIMING) + 1)
        ]
        self.assertThat(
            mock_addErrback, MockCallsMatch(*expected_errback_calls)
        )

    @inlineCallbacks
    def test_run_logs_result_and_makes_properties_available(self):
        logger = self.useFixture(TwistedLoggerFixture())
        monitor = DHCPRequestMonitor("lo")
        mock_send_and_await = self.patch(
            monitor, "send_requests_and_await_replies"
        )
        mock_send_and_await.return_value = {
            DHCPServer("127.0.0.1", "127.0.0.1"),
            DHCPServer("127.1.1.1", "127.2.2.2"),
        }
        yield monitor.run()
        self.assertThat(mock_send_and_await, MockCallsMatch(call()))
        self.assertThat(
            logger.output,
            DocTestMatches(
                "External DHCP server(s) discovered on interface 'lo': 127.0.0.1, "
                "127.1.1.1 (via 127.2.2.2)"
            ),
        )
        self.assertEqual({"127.0.0.1", "127.1.1.1"}, monitor.dhcp_servers)
        self.assertEqual({"127.0.0.1", "127.2.2.2"}, monitor.dhcp_addresses)

    @inlineCallbacks
    def test_run_skips_logging_if_no_servers_found(self):
        logger = self.useFixture(TwistedLoggerFixture())
        monitor = DHCPRequestMonitor("lo")
        mock_send_and_await = self.patch(
            monitor, "send_requests_and_await_replies"
        )
        mock_send_and_await.return_value = {}
        yield monitor.run()
        self.assertThat(mock_send_and_await, MockCallsMatch(call()))
        self.assertThat(logger.output, DocTestMatches(""))

    @inlineCallbacks
    def test_run_via_probe_interface_returns_servers(self):
        mock_send_and_await = self.patch(
            DHCPRequestMonitor, "send_requests_and_await_replies"
        )
        mock_send_and_await.return_value = {
            DHCPServer("127.0.0.1", "127.0.0.1"),
            DHCPServer("127.1.1.1", "127.2.2.2"),
        }
        result = yield probe_interface("lo")
        self.assertThat(mock_send_and_await, MockCallsMatch(call()))
        self.assertEqual({"127.0.0.1", "127.1.1.1"}, result)
