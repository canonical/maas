# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test parser for 'ip route list proto static'."""


import random
from unittest.mock import sentinel

from maastesting.factory import factory
from maastesting.matchers import MockCalledOnceWith
from maastesting.testcase import MAASTestCase
from provisioningserver.utils import iproute as iproute_module
from provisioningserver.utils.iproute import (
    _parse_route_definition,
    get_ip_route,
    parse_ip_route,
)


class TestHelperFunctions(MAASTestCase):
    def test_parse_route_with_proto_and_metric(self):
        network = factory.make_ipv4_network()
        subnet = str(network.cidr)
        gateway = factory.pick_ip_in_network(network)
        interface = factory.make_name("nic")
        proto = factory.make_name("proto")
        metric = random.randint(50, 100)
        route_line = "%s via %s dev %s proto %s metric %d" % (
            subnet,
            gateway,
            interface,
            proto,
            metric,
        )
        self.assertEquals(
            (
                subnet,
                {
                    "via": gateway,
                    "dev": interface,
                    "proto": proto,
                    "metric": metric,
                },
            ),
            _parse_route_definition(route_line),
        )

    def test_parse_route_without_proto_or_metric(self):
        network = factory.make_ipv4_network()
        subnet = str(network.cidr)
        gateway = factory.pick_ip_in_network(network)
        interface = factory.make_name("nic")
        route_line = "%s via %s dev %s" % (subnet, gateway, interface)
        self.assertEquals(
            (subnet, {"via": gateway, "dev": interface}),
            _parse_route_definition(route_line),
        )


class TestParseIPRoute(MAASTestCase):
    def make_route_line(self, subnet=None):
        network = factory.make_ipv4_network()
        gateway = factory.pick_ip_in_network(network)
        if subnet is None:
            subnet = str(network.cidr)
        interface = factory.make_name("nic")
        route_line = "%s via %s dev %s" % (subnet, gateway, interface)
        return route_line, {subnet: {"via": gateway, "dev": interface}}

    def test_returns_routes_definition(self):
        route_input, expected_output = self.make_route_line(subnet="default")
        for _ in range(3):
            route_line, output = self.make_route_line()
            expected_output.update(output)
            route_input += "\n" + route_line
        route_input += "\n"
        self.assertEquals(expected_output, parse_ip_route(route_input))


class TestGetIPRoute(MAASTestCase):
    def test_calls_methods(self):
        patch_call_and_check = self.patch(iproute_module, "call_and_check")
        patch_call_and_check.return_value = sentinel.ip_route_cmd
        patch_parse_ip_route = self.patch(iproute_module, "parse_ip_route")
        patch_parse_ip_route.return_value = sentinel.output
        self.assertEquals(sentinel.output, get_ip_route())
        self.assertThat(
            patch_call_and_check,
            MockCalledOnceWith(["ip", "route", "list", "scope", "global"]),
        )
        self.assertThat(
            patch_parse_ip_route, MockCalledOnceWith(sentinel.ip_route_cmd)
        )
