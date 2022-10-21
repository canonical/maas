# Copyright 2017 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for ``provisioningserver.utils.send_beacons``."""


from argparse import ArgumentParser
import io
from unittest.mock import ANY, Mock

from testtools.matchers import MatchesStructure
from twisted import internet
from twisted.internet.task import Clock

from maastesting.factory import factory
from maastesting.matchers import Matches, MockCalledOnceWith, MockNotCalled
from maastesting.testcase import MAASTestCase
from provisioningserver.tests.test_security import SharedSecretTestCase
from provisioningserver.utils import send_beacons as send_beacons_module
from provisioningserver.utils.env import MAAS_SECRET
from provisioningserver.utils.send_beacons import add_arguments, run


def ArgumentsMatching(**kwargs):
    """Tests if the output from `argparse` matches our expectations."""
    return Matches(MatchesStructure.byEquality(**kwargs))


TEST_INTERFACES = {
    "eth0": {"links": []},
    "eth1": {"links": [{"address": "192.168.0.1/24"}]},
    "eth2": {
        "links": [
            {"address": "192.168.2.1/24"},
            {"address": "192.168.3.1/24"},
            {"address": "2001:db8::1/64"},
        ]
    },
}


class SendBeaconsTestCase(MAASTestCase):
    def setUp(self):
        super().setUp()
        self.output = io.StringIO()
        self.error_output = io.StringIO()
        self.all_interfaces_mock = self.patch(
            send_beacons_module, "get_all_interfaces_definition"
        )
        # Prevent logging from being reconfigured inside the test suite.
        self.logger_mock = self.patch(send_beacons_module, "logger")
        self.all_interfaces_mock.return_value = TEST_INTERFACES
        self.parser = ArgumentParser()
        add_arguments(self.parser)

    def run_command(self, *args):
        parsed_args = self.parser.parse_args([*args])
        return run(parsed_args, stdout=self.output)


class TestSendBeaconsCommand(SendBeaconsTestCase):
    def setUp(self):
        super().setUp()
        self.send_beacons_mock = self.patch(send_beacons_module.do_beaconing)

    def test_default_arguments(self):
        self.run_command()
        self.assertThat(
            self.send_beacons_mock,
            MockCalledOnceWith(
                ArgumentsMatching(
                    source=None, destination=None, timeout=5, port=0
                ),
                interfaces=TEST_INTERFACES,
            ),
        )

    def test_interprets_long_arguments(self):
        self.run_command(
            "--verbose",
            "--source",
            "1.1.1.1",
            "--timeout",
            "42",
            "--port",
            "4242",
            "2.2.2.2",
        )
        self.assertThat(
            self.send_beacons_mock,
            MockCalledOnceWith(
                ArgumentsMatching(
                    source="1.1.1.1",
                    destination="2.2.2.2",
                    timeout=42,
                    port=4242,
                ),
                interfaces=TEST_INTERFACES,
            ),
        )

    def test_interprets_short_arguments(self):
        self.run_command(
            "-v", "-s", "1.1.1.1", "-t", "42", "-p", "4242", "2.2.2.2"
        )
        self.assertThat(
            self.send_beacons_mock,
            MockCalledOnceWith(
                ArgumentsMatching(
                    source="1.1.1.1",
                    destination="2.2.2.2",
                    timeout=42,
                    port=4242,
                ),
                interfaces=TEST_INTERFACES,
            ),
        )


class FakeBeaconingSocketProtocol:
    """Fake BeaconingSocketProtocol."""

    tx_queue = []
    rx_queue = []
    topology_hints = []


class TestSendBeaconsProtocolInteraction(
    SendBeaconsTestCase, SharedSecretTestCase
):
    def setUp(self):
        super().setUp()
        MAAS_SECRET.set(factory.make_bytes())
        self.protocol_mock = self.patch(
            send_beacons_module, "BeaconingSocketProtocol"
        )
        self.fake_protocol = FakeBeaconingSocketProtocol()
        self.protocol_mock.return_value = self.fake_protocol
        self.fake_protocol.send_multicast_beacons = Mock()
        self.fake_protocol.send_beacon = Mock()
        # Prevent the command from starting and stopping the reactor.
        self.reactor_mock = self.patch(internet, "reactor", Clock())
        self.patch(self.reactor_mock, "run")

    def test_sends_multicast_beacons_by_default(self):
        self.run_command()
        self.assertThat(
            self.protocol_mock,
            MockCalledOnceWith(
                ANY,
                debug=True,
                interface="::",
                port=0,
                process_incoming=True,
                interfaces=TEST_INTERFACES,
            ),
        )
        self.assertThat(self.fake_protocol.send_beacon, MockNotCalled())
        self.assertThat(
            self.fake_protocol.send_multicast_beacons,
            MockCalledOnceWith(TEST_INTERFACES, verbose=False),
        )

    def test_sends_multicast_beacons_with_verbose_flag(self):
        self.run_command(
            "--verbose",
            "--source",
            "1.1.1.1",
            "--timeout",
            "42",
            "--port",
            "4242",
        )
        self.assertThat(
            self.protocol_mock,
            MockCalledOnceWith(
                ANY,
                debug=True,
                interface="1.1.1.1",
                port=4242,
                process_incoming=True,
                interfaces=TEST_INTERFACES,
            ),
        )
        self.assertThat(self.fake_protocol.send_beacon, MockNotCalled())
        self.assertThat(
            self.fake_protocol.send_multicast_beacons,
            MockCalledOnceWith(TEST_INTERFACES, verbose=True),
        )

    def test_sends_unicast_beacon(self):
        self.run_command(
            "-v", "-s", "1.1.1.1", "-t", "42", "-p", "4242", "127.0.0.1"
        )
        self.assertThat(
            self.protocol_mock,
            MockCalledOnceWith(
                ANY,
                debug=True,
                interface="1.1.1.1",
                port=4242,
                process_incoming=True,
                interfaces=TEST_INTERFACES,
            ),
        )
        self.assertThat(
            self.fake_protocol.send_multicast_beacons, MockNotCalled()
        )
        self.assertThat(
            self.fake_protocol.send_beacon,
            MockCalledOnceWith(ANY, ("::ffff:127.0.0.1", 5240)),
        )
