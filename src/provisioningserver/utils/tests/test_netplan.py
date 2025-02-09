# Copyright 2017 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for netplan helpers."""

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
        self.assertEqual(
            netplan_params,
            {"down-delay": 100, "mode": "active-backup", "up-delay": 200},
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
        self.assertIn("unknown bond option", logger.output)
        self.assertEqual(netplan_params, {"mode": "active-backup"})

    def test_skips_and_logs_parameters_with_no_netplan_equivalent(self):
        with TwistedLoggerFixture() as logger:
            netplan_params = get_netplan_bond_parameters(
                {"bond-queue-id": 100, "bond-mode": "active-backup"}
            )
        self.assertIn(
            "no netplan equivalent for bond option",
            logger.output,
        )
        self.assertEqual(netplan_params, {"mode": "active-backup"})

    def test_converts_arp_ip_target_to_list(self):
        netplan_params = get_netplan_bond_parameters(
            {"bond-arp-ip-target": "192.168.0.1"}
        )
        self.assertEqual(netplan_params, {"arp-ip-targets": ["192.168.0.1"]})

    def test_converts_arp_ip_target_to_list_multiple_ips(self):
        netplan_params = get_netplan_bond_parameters(
            {"bond-arp-ip-target": "192.168.0.1 fe80::1"}
        )
        self.assertEqual(
            netplan_params, {"arp-ip-targets": ["192.168.0.1", "fe80::1"]}
        )

    def test_converts_arp_ip_target_to_list_with_weird_whitespace(self):
        netplan_params = get_netplan_bond_parameters(
            {"bond-arp-ip-target": "  192.168.0.1    fe80::1    "}
        )
        self.assertEqual(
            netplan_params, {"arp-ip-targets": ["192.168.0.1", "fe80::1"]}
        )


class TestGetNetplanBridgeParameters(MAASTestCase):
    def test_converts_parameter_names(self):
        netplan_params = get_netplan_bridge_parameters(
            {"bridge_ageing": 5, "bridge_maxage": 10, "bridge_stp": True}
        )
        self.assertEqual(
            netplan_params, {"ageing-time": 5, "max-age": 10, "stp": True}
        )

    def test_skips_and_logs_unknown_parameters(self):
        with TwistedLoggerFixture() as logger:
            netplan_params = get_netplan_bridge_parameters(
                {"xbridge_ageing": 5, "bridge_maxage": 10, "xbridge_stp": True}
            )
        self.assertIn(
            "unknown bridge option",
            logger.output,
        )
        self.assertEqual(netplan_params, {"max-age": 10})

    def test_skips_and_logs_parameters_with_no_netplan_equivalent(self):
        with TwistedLoggerFixture() as logger:
            netplan_params = get_netplan_bridge_parameters(
                {"bridge_waitport": True, "bridge_maxage": 10}
            )
        self.assertIn(
            "no netplan equivalent for bridge option",
            logger.output,
        )
        self.assertEqual(netplan_params, {"max-age": 10})
