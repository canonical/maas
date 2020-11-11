# Copyright 2017 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for netplan helpers."""


from textwrap import dedent

from testtools.matchers import Equals

from maastesting.matchers import DocTestMatches
from maastesting.testcase import MAASTestCase
from maastesting.twisted import TwistedLoggerFixture
from provisioningserver.utils.netplan import (
    get_netplan_bond_parameters,
    get_netplan_bridge_parameters,
)


class TestGetNetplanBondParameters(MAASTestCase):
    def test_converts_parameter_names(self):
        netplan_params = get_netplan_bond_parameters(
            {
                "bond-downdelay": 100,
                "bond-mode": "active-backup",
                "bond-updelay": 200,
            }
        )
        self.expectThat(
            netplan_params,
            Equals(
                {"down-delay": 100, "mode": "active-backup", "up-delay": 200}
            ),
        )

    def test_skips_and_logs_unknown_parameters(self):
        with TwistedLoggerFixture() as logger:
            netplan_params = get_netplan_bond_parameters(
                {
                    "xbond-downdelay": 100,
                    "bond-mode": "active-backup",
                    "xbond-updelay": 200,
                }
            )
        self.assertThat(
            logger.output,
            DocTestMatches(
                dedent(
                    """\
                ...unknown bond option..."""
                )
            ),
        )
        self.expectThat(netplan_params, Equals({"mode": "active-backup"}))

    def test_skips_and_logs_parameters_with_no_netplan_equivalent(self):
        with TwistedLoggerFixture() as logger:
            netplan_params = get_netplan_bond_parameters(
                {"bond-queue-id": 100, "bond-mode": "active-backup"}
            )
        self.assertThat(
            logger.output,
            DocTestMatches(
                dedent(
                    """\
                ...no netplan equivalent for bond option..."""
                )
            ),
        )
        self.expectThat(netplan_params, Equals({"mode": "active-backup"}))

    def test_converts_arp_ip_target_to_list(self):
        netplan_params = get_netplan_bond_parameters(
            {"bond-arp-ip-target": "192.168.0.1"}
        )
        self.expectThat(
            netplan_params, Equals({"arp-ip-targets": ["192.168.0.1"]})
        )

    def test_converts_arp_ip_target_to_list_multiple_ips(self):
        netplan_params = get_netplan_bond_parameters(
            {"bond-arp-ip-target": "192.168.0.1 fe80::1"}
        )
        self.expectThat(
            netplan_params,
            Equals({"arp-ip-targets": ["192.168.0.1", "fe80::1"]}),
        )

    def test_converts_arp_ip_target_to_list_with_weird_whitespace(self):
        netplan_params = get_netplan_bond_parameters(
            {"bond-arp-ip-target": "  192.168.0.1    fe80::1    "}
        )
        self.expectThat(
            netplan_params,
            Equals({"arp-ip-targets": ["192.168.0.1", "fe80::1"]}),
        )


class TestGetNetplanBridgeParameters(MAASTestCase):
    def test_converts_parameter_names(self):
        netplan_params = get_netplan_bridge_parameters(
            {"bridge_ageing": 5, "bridge_maxage": 10, "bridge_stp": True}
        )
        self.expectThat(
            netplan_params,
            Equals({"ageing-time": 5, "max-age": 10, "stp": True}),
        )

    def test_skips_and_logs_unknown_parameters(self):
        with TwistedLoggerFixture() as logger:
            netplan_params = get_netplan_bridge_parameters(
                {"xbridge_ageing": 5, "bridge_maxage": 10, "xbridge_stp": True}
            )
        self.assertThat(
            logger.output,
            DocTestMatches(
                dedent(
                    """\
                ...unknown bridge option..."""
                )
            ),
        )
        self.expectThat(netplan_params, Equals({"max-age": 10}))

    def test_skips_and_logs_parameters_with_no_netplan_equivalent(self):
        with TwistedLoggerFixture() as logger:
            netplan_params = get_netplan_bridge_parameters(
                {"bridge_waitport": True, "bridge_maxage": 10}
            )
        self.assertThat(
            logger.output,
            DocTestMatches(
                dedent(
                    """\
                ...no netplan equivalent for bridge option..."""
                )
            ),
        )
        self.expectThat(netplan_params, Equals({"max-age": 10}))
