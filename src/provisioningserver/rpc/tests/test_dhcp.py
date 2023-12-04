# Copyright 2014-2018 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for :py:module:`~provisioningserver.rpc.dhcp`."""


import copy
from operator import itemgetter
from unittest import TestCase
from unittest.mock import ANY, call, Mock, sentinel

from fixtures import FakeLogger
from twisted.internet.defer import inlineCallbacks

from maastesting import get_testing_timeout
from maastesting.factory import factory
from maastesting.testcase import MAASTestCase, MAASTwistedRunTest
from provisioningserver.dhcp.omapi import OmapiError
from provisioningserver.dhcp.testing.config import (
    DHCPConfigNameResolutionDisabled,
    fix_shared_networks_failover,
    make_failover_peer_config,
    make_global_dhcp_snippets,
    make_host,
    make_host_dhcp_snippets,
    make_interface,
    make_shared_network,
    make_subnet_dhcp_snippets,
)
from provisioningserver.rpc import dhcp, exceptions
from provisioningserver.utils.service_monitor import (
    SERVICE_STATE,
    ServiceActionError,
    ServiceState,
)
from provisioningserver.utils.shell import ExternalProcessError


class TestDHCPState(MAASTestCase):
    def make_args(self):
        omapi_key = factory.make_name("omapi_key")
        failover_peers = [make_failover_peer_config() for _ in range(3)]
        shared_networks = [make_shared_network() for _ in range(3)]
        shared_networks = fix_shared_networks_failover(
            shared_networks, failover_peers
        )
        hosts = [make_host() for _ in range(3)]
        interfaces = [make_interface() for _ in range(3)]
        return (
            omapi_key,
            failover_peers,
            shared_networks,
            hosts,
            interfaces,
            make_global_dhcp_snippets(),
        )

    def test_new_sorts_properties(self):
        (
            omapi_key,
            failover_peers,
            shared_networks,
            hosts,
            interfaces,
            global_dhcp_snippets,
        ) = self.make_args()
        state = dhcp.DHCPState(
            omapi_key,
            failover_peers,
            shared_networks,
            hosts,
            interfaces,
            global_dhcp_snippets,
        )
        self.assertEqual(state.omapi_key, omapi_key)
        self.assertEqual(
            state.failover_peers,
            sorted(failover_peers, key=itemgetter("name")),
        )
        self.assertEqual(
            state.shared_networks,
            sorted(shared_networks, key=itemgetter("name")),
        )
        self.assertEqual(state.hosts, {host["mac"]: host for host in hosts})

        self.assertEqual(
            state.interfaces,
            sorted(interface["name"] for interface in interfaces),
        )
        self.assertEqual(
            state.global_dhcp_snippets,
            sorted(global_dhcp_snippets, key=itemgetter("name")),
        )

    def test_requires_restart_returns_True_when_omapi_key_different(self):
        (
            omapi_key,
            failover_peers,
            shared_networks,
            hosts,
            interfaces,
            global_dhcp_snippets,
        ) = self.make_args()
        state = dhcp.DHCPState(
            omapi_key,
            failover_peers,
            shared_networks,
            hosts,
            interfaces,
            global_dhcp_snippets,
        )
        new_state = dhcp.DHCPState(
            factory.make_name("new_omapi_key"),
            copy.deepcopy(failover_peers),
            copy.deepcopy(shared_networks),
            copy.deepcopy(hosts),
            copy.deepcopy(interfaces),
            copy.deepcopy(global_dhcp_snippets),
        )
        self.assertTrue(new_state.requires_restart(state))

    def test_requires_restart_returns_False_when_hosts_are_ipv4_and_server_is_ipv4(
        self,
    ):
        (
            omapi_key,
            failover_peers,
            shared_networks,
            _,
            interfaces,
            global_dhcp_snippets,
        ) = self.make_args()
        state = dhcp.DHCPState(
            omapi_key,
            failover_peers,
            shared_networks,
            [],
            interfaces,
            global_dhcp_snippets,
        )
        new_hosts = [make_host(dhcp_snippets=[]) for _ in range(3)]
        new_state = dhcp.DHCPState(
            omapi_key,
            copy.deepcopy(failover_peers),
            copy.deepcopy(shared_networks),
            new_hosts,
            copy.deepcopy(interfaces),
            copy.deepcopy(global_dhcp_snippets),
        )
        self.assertFalse(
            new_state.requires_restart(state, is_dhcpv6_server=False)
        )

    def test_requires_restart_returns_True_when_hosts_are_ipv6_and_server_is_ipv4(
        self,
    ):
        (
            omapi_key,
            failover_peers,
            shared_networks,
            _,
            interfaces,
            global_dhcp_snippets,
        ) = self.make_args()
        state = dhcp.DHCPState(
            omapi_key,
            failover_peers,
            shared_networks,
            [],
            interfaces,
            global_dhcp_snippets,
        )
        new_hosts = [make_host(dhcp_snippets=[], ipv6=True) for _ in range(3)]
        new_state = dhcp.DHCPState(
            omapi_key,
            copy.deepcopy(failover_peers),
            copy.deepcopy(shared_networks),
            new_hosts,
            copy.deepcopy(interfaces),
            copy.deepcopy(global_dhcp_snippets),
        )
        self.assertTrue(
            new_state.requires_restart(state, is_dhcpv6_server=False)
        )

    def test_requires_restart_returns_False_when_hosts_are_ipv6_and_server_is_ipv6(
        self,
    ):
        (
            omapi_key,
            failover_peers,
            shared_networks,
            _,
            interfaces,
            global_dhcp_snippets,
        ) = self.make_args()
        state = dhcp.DHCPState(
            omapi_key,
            failover_peers,
            shared_networks,
            [],
            interfaces,
            global_dhcp_snippets,
        )
        new_hosts = [make_host(dhcp_snippets=[], ipv6=True) for _ in range(3)]
        new_state = dhcp.DHCPState(
            omapi_key,
            copy.deepcopy(failover_peers),
            copy.deepcopy(shared_networks),
            new_hosts,
            copy.deepcopy(interfaces),
            copy.deepcopy(global_dhcp_snippets),
        )
        self.assertFalse(
            new_state.requires_restart(state, is_dhcpv6_server=True)
        )

    def test_requires_restart_returns_True_when_failover_different(self):
        (
            omapi_key,
            failover_peers,
            shared_networks,
            hosts,
            interfaces,
            global_dhcp_snippets,
        ) = self.make_args()
        state = dhcp.DHCPState(
            omapi_key,
            failover_peers,
            shared_networks,
            hosts,
            interfaces,
            global_dhcp_snippets,
        )
        changed_failover_peers = copy.deepcopy(failover_peers)
        changed_failover_peers[0]["name"] = factory.make_name("failover")
        new_state = dhcp.DHCPState(
            omapi_key,
            changed_failover_peers,
            copy.deepcopy(shared_networks),
            copy.deepcopy(hosts),
            copy.deepcopy(interfaces),
            copy.deepcopy(global_dhcp_snippets),
        )
        self.assertTrue(new_state.requires_restart(state))

    def test_requires_restart_returns_True_when_network_different(self):
        (
            omapi_key,
            failover_peers,
            shared_networks,
            hosts,
            interfaces,
            global_dhcp_snippets,
        ) = self.make_args()
        state = dhcp.DHCPState(
            omapi_key,
            failover_peers,
            shared_networks,
            hosts,
            interfaces,
            global_dhcp_snippets,
        )
        changed_shared_networks = copy.deepcopy(shared_networks)
        changed_shared_networks[0]["name"] = factory.make_name("network")
        new_state = dhcp.DHCPState(
            omapi_key,
            copy.deepcopy(failover_peers),
            changed_shared_networks,
            copy.deepcopy(hosts),
            copy.deepcopy(interfaces),
            copy.deepcopy(global_dhcp_snippets),
        )
        self.assertTrue(new_state.requires_restart(state))

    def test_requires_restart_returns_True_when_interfaces_different(self):
        (
            omapi_key,
            failover_peers,
            shared_networks,
            hosts,
            interfaces,
            global_dhcp_snippets,
        ) = self.make_args()
        state = dhcp.DHCPState(
            omapi_key,
            failover_peers,
            shared_networks,
            hosts,
            interfaces,
            global_dhcp_snippets,
        )
        changed_interfaces = copy.deepcopy(interfaces)
        changed_interfaces[0]["name"] = factory.make_name("eth")
        new_state = dhcp.DHCPState(
            omapi_key,
            copy.deepcopy(failover_peers),
            copy.deepcopy(shared_networks),
            copy.deepcopy(hosts),
            changed_interfaces,
            copy.deepcopy(global_dhcp_snippets),
        )
        self.assertTrue(new_state.requires_restart(state))

    def test_requires_restart_returns_False_when_all_the_same(self):
        (
            omapi_key,
            failover_peers,
            shared_networks,
            hosts,
            interfaces,
            global_dhcp_snippets,
        ) = self.make_args()
        state = dhcp.DHCPState(
            omapi_key,
            failover_peers,
            shared_networks,
            hosts,
            interfaces,
            global_dhcp_snippets,
        )
        new_state = dhcp.DHCPState(
            omapi_key,
            copy.deepcopy(failover_peers),
            copy.deepcopy(shared_networks),
            copy.deepcopy(hosts),
            copy.deepcopy(interfaces),
            copy.deepcopy(global_dhcp_snippets),
        )
        self.assertFalse(new_state.requires_restart(state))

    def test_requires_restart_returns_False_when_hosts_different(self):
        (
            omapi_key,
            failover_peers,
            shared_networks,
            hosts,
            interfaces,
            global_dhcp_snippets,
        ) = self.make_args()
        state = dhcp.DHCPState(
            omapi_key,
            failover_peers,
            shared_networks,
            hosts,
            interfaces,
            global_dhcp_snippets,
        )
        changed_hosts = copy.deepcopy(hosts)
        changed_hosts.append(make_host(dhcp_snippets=[]))
        new_state = dhcp.DHCPState(
            omapi_key,
            copy.deepcopy(failover_peers),
            copy.deepcopy(shared_networks),
            changed_hosts,
            copy.deepcopy(interfaces),
            copy.deepcopy(global_dhcp_snippets),
        )
        self.assertFalse(new_state.requires_restart(state))

    def test_requires_restart_True_when_global_dhcp_snippets_diff(self):
        (
            omapi_key,
            failover_peers,
            shared_networks,
            hosts,
            interfaces,
            global_dhcp_snippets,
        ) = self.make_args()
        state = dhcp.DHCPState(
            omapi_key,
            failover_peers,
            shared_networks,
            hosts,
            interfaces,
            global_dhcp_snippets,
        )
        changed_global_dhcp_snippets = make_global_dhcp_snippets(
            allow_empty=False
        )
        new_state = dhcp.DHCPState(
            omapi_key,
            copy.deepcopy(failover_peers),
            copy.deepcopy(shared_networks),
            copy.deepcopy(hosts),
            copy.deepcopy(interfaces),
            changed_global_dhcp_snippets,
        )
        self.assertTrue(new_state.requires_restart(state))

    def test_requires_restart_True_when_subnet_dhcp_snippets_diff(self):
        (
            omapi_key,
            failover_peers,
            shared_networks,
            hosts,
            interfaces,
            global_dhcp_snippets,
        ) = self.make_args()
        state = dhcp.DHCPState(
            omapi_key,
            failover_peers,
            shared_networks,
            hosts,
            interfaces,
            global_dhcp_snippets,
        )
        changed_shared_networks = copy.deepcopy(shared_networks)
        for shared_network in changed_shared_networks:
            for subnet in shared_network["subnets"]:
                subnet["dhcp_snippets"] = make_subnet_dhcp_snippets(
                    allow_empty=False
                )
        new_state = dhcp.DHCPState(
            omapi_key,
            copy.deepcopy(failover_peers),
            changed_shared_networks,
            copy.deepcopy(hosts),
            copy.deepcopy(interfaces),
            copy.deepcopy(global_dhcp_snippets),
        )
        self.assertTrue(new_state.requires_restart(state))

    def test_requires_restart_True_when_hosts_dhcp_snippets_diff(self):
        (
            omapi_key,
            failover_peers,
            shared_networks,
            hosts,
            interfaces,
            global_dhcp_snippets,
        ) = self.make_args()
        state = dhcp.DHCPState(
            omapi_key,
            failover_peers,
            shared_networks,
            hosts,
            interfaces,
            global_dhcp_snippets,
        )
        changed_hosts = copy.deepcopy(hosts)
        for host in changed_hosts:
            host["dhcp_snippets"] = make_host_dhcp_snippets(allow_empty=False)
        new_state = dhcp.DHCPState(
            omapi_key,
            copy.deepcopy(failover_peers),
            copy.deepcopy(shared_networks),
            changed_hosts,
            copy.deepcopy(interfaces),
            copy.deepcopy(global_dhcp_snippets),
        )
        self.assertTrue(new_state.requires_restart(state))

    def test_host_diff_returns_removal_added_and_modify(self):
        (
            omapi_key,
            failover_peers,
            shared_networks,
            hosts,
            interfaces,
            global_dhcp_snippets,
        ) = self.make_args()
        state = dhcp.DHCPState(
            omapi_key,
            failover_peers,
            shared_networks,
            hosts,
            interfaces,
            global_dhcp_snippets,
        )
        changed_hosts = copy.deepcopy(hosts)
        removed_host = changed_hosts.pop()
        modified_host = changed_hosts[0]
        modified_host["ip"] = factory.make_ip_address()
        added_host = make_host()
        changed_hosts.append(added_host)
        new_state = dhcp.DHCPState(
            omapi_key,
            copy.deepcopy(failover_peers),
            copy.deepcopy(shared_networks),
            changed_hosts,
            copy.deepcopy(interfaces),
            copy.deepcopy(global_dhcp_snippets),
        )
        self.assertEqual(
            ([removed_host], [added_host], [modified_host]),
            new_state.host_diff(state),
        )

    def test_get_config_returns_config_and_calls_with_params(self):
        mock_get_config = self.patch_autospec(dhcp, "get_config")
        mock_get_config.return_value = sentinel.config
        (
            omapi_key,
            failover_peers,
            shared_networks,
            hosts,
            interfaces,
            global_dhcp_snippets,
        ) = self.make_args()
        state = dhcp.DHCPState(
            omapi_key,
            failover_peers,
            shared_networks,
            hosts,
            interfaces,
            global_dhcp_snippets,
        )
        server = Mock()
        self.assertEqual(
            (sentinel.config, " ".join(state.interfaces)),
            state.get_config(server),
        )
        mock_get_config.assert_called_once_with(
            server.template_basename,
            omapi_key=omapi_key,
            ipv6=ANY,
            failover_peers=state.failover_peers,
            shared_networks=state.shared_networks,
            hosts=sorted(state.hosts.values(), key=itemgetter("host")),
            global_dhcp_snippets=sorted(
                global_dhcp_snippets, key=itemgetter("name")
            ),
        )


class TestUpdateHosts(MAASTestCase):
    def test_creates_client_with_correct_arguments(self):
        omapi_cli = self.patch(dhcp, "OmapiClient")
        server = Mock()
        server.ipv6 = factory.pick_bool()
        dhcp._update_hosts(server, [], [], [])
        omapi_cli.assert_called_once_with(server.omapi_key, server.ipv6)

    def test_performs_operations(self):
        remove_host = make_host()
        add_host = make_host()
        modify_host = make_host()
        omapi_cli = Mock()
        self.patch(dhcp, "OmapiClient").return_value = omapi_cli
        dhcp._update_hosts(Mock(), [remove_host], [add_host], [modify_host])
        self.assertEqual(
            omapi_cli.mock_calls,
            [
                call.del_host(remove_host["mac"]),
                call.add_host(add_host["mac"], add_host["ip"]),
                call.update_host(modify_host["mac"], modify_host["ip"]),
            ],
        )

    def test_fail_remove(self):
        host = make_host()
        omapi_cli = Mock()
        omapi_cli.del_host.side_effect = OmapiError("Fail")
        self.patch(dhcp, "OmapiClient").return_value = omapi_cli
        err = self.assertRaises(
            exceptions.CannotRemoveHostMap,
            dhcp._update_hosts,
            Mock(),
            [host],
            [],
            [],
        )
        self.assertEqual(str(err), "Fail")

    def test_fail_create(self):
        host = make_host()
        omapi_cli = Mock()
        omapi_cli.add_host.side_effect = OmapiError("Fail")
        self.patch(dhcp, "OmapiClient").return_value = omapi_cli
        err = self.assertRaises(
            exceptions.CannotCreateHostMap,
            dhcp._update_hosts,
            Mock(),
            [],
            [host],
            [],
        )
        self.assertEqual(str(err), "Fail")

    def test_fail_modify(self):
        host = make_host()
        omapi_cli = Mock()
        omapi_cli.update_host.side_effect = OmapiError("Fail")
        self.patch(dhcp, "OmapiClient").return_value = omapi_cli
        err = self.assertRaises(
            exceptions.CannotModifyHostMap,
            dhcp._update_hosts,
            Mock(),
            [],
            [],
            [host],
        )
        self.assertEqual(str(err), "Fail")


class TestConfigureDHCP(MAASTestCase):
    run_tests_with = MAASTwistedRunTest.make_factory(
        timeout=get_testing_timeout()
    )

    scenarios = (
        ("DHCPv4", {"server": dhcp.DHCPv4Server}),
        ("DHCPv6", {"server": dhcp.DHCPv6Server}),
    )

    assertRaises = TestCase.assertRaises

    def setUp(self):
        super().setUp()
        # The service monitor is an application global and so are the services
        # it monitors, and tests must leave them as they found them.
        self.addCleanup(dhcp.service_monitor.getServiceByName("dhcpd").off)
        self.addCleanup(dhcp.service_monitor.getServiceByName("dhcpd6").off)
        # The dhcp server states are global so we clean them after each test.
        self.addCleanup(dhcp._current_server_state.clear)
        # Temporarily prevent hostname resolution when generating DHCP
        # configuration. This is tested elsewhere.
        self.useFixture(DHCPConfigNameResolutionDisabled())

    def configure(
        self,
        omapi_key,
        failover_peers,
        shared_networks,
        hosts,
        interfaces,
        dhcp_snippets,
    ):
        server = self.server(omapi_key)
        return dhcp.configure(
            server,
            failover_peers,
            shared_networks,
            hosts,
            interfaces,
            dhcp_snippets,
        )

    def patch_os_exists(self):
        return self.patch_autospec(dhcp.os.path, "exists")

    def patch_sudo_delete_file(self):
        return self.patch_autospec(dhcp, "sudo_delete_file")

    def patch_sudo_write_file(self):
        return self.patch_autospec(dhcp, "sudo_write_file")

    def patch_restartService(self):
        return self.patch(dhcp.service_monitor, "restartService")

    def patch_ensureService(self):
        return self.patch(dhcp.service_monitor, "ensureService")

    def patch_getServiceState(self):
        return self.patch(dhcp.service_monitor, "getServiceState")

    def patch_get_config(self):
        return self.patch_autospec(dhcp, "get_config")

    def patch_update_hosts(self):
        return self.patch(dhcp, "_update_hosts")

    @inlineCallbacks
    def test_deletes_dhcp_config_if_no_subnets_defined(self):
        mock_exists = self.patch_os_exists()
        mock_exists.return_value = True
        mock_sudo_delete = self.patch_sudo_delete_file()
        dhcp_service = dhcp.service_monitor.getServiceByName(
            self.server.dhcp_service
        )
        self.patch_autospec(dhcp_service, "off")
        self.patch_restartService()
        self.patch_ensureService()
        yield self.configure(factory.make_name("key"), [], [], [], [], [])
        mock_sudo_delete.assert_called_once_with(self.server.config_filename)

    @inlineCallbacks
    def test_stops_dhcp_server_if_no_subnets_defined(self):
        mock_exists = self.patch_os_exists()
        mock_exists.return_value = False
        dhcp_service = dhcp.service_monitor.getServiceByName(
            self.server.dhcp_service
        )
        off = self.patch_autospec(dhcp_service, "off")
        restart_service = self.patch_restartService()
        ensure_service = self.patch_ensureService()
        yield self.configure(factory.make_name("key"), [], [], [], [], [])
        off.assert_called_once_with()
        ensure_service.assert_called_once_with(self.server.dhcp_service)
        restart_service.assert_not_called()

    @inlineCallbacks
    def test_stops_dhcp_server_clears_state(self):
        dhcp._current_server_state[self.server.dhcp_service] = sentinel.state
        mock_exists = self.patch_os_exists()
        mock_exists.return_value = False
        dhcp_service = dhcp.service_monitor.getServiceByName(
            self.server.dhcp_service
        )
        self.patch_autospec(dhcp_service, "off")
        self.patch_restartService()
        self.patch_ensureService()
        yield self.configure(factory.make_name("key"), [], [], [], [], [])
        self.assertIsNone(dhcp._current_server_state[self.server.dhcp_service])

    @inlineCallbacks
    def test_writes_config_and_calls_restart_when_no_current_state(self):
        write_file = self.patch_sudo_write_file()
        restart_service = self.patch_restartService()

        failover_peers = make_failover_peer_config()
        shared_network = make_shared_network()
        [shared_network] = fix_shared_networks_failover(
            [shared_network], [failover_peers]
        )
        host = make_host()
        interface = make_interface()
        global_dhcp_snippets = make_global_dhcp_snippets()
        expected_config = factory.make_name("config")
        self.patch_get_config().return_value = expected_config

        dhcp_service = dhcp.service_monitor.getServiceByName(
            self.server.dhcp_service
        )
        on = self.patch_autospec(dhcp_service, "on")

        omapi_key = factory.make_name("omapi_key")
        yield self.configure(
            omapi_key,
            [failover_peers],
            [shared_network],
            [host],
            [interface],
            global_dhcp_snippets,
        )

        write_file.assert_has_calls(
            [
                call(
                    self.server.config_filename,
                    expected_config.encode("utf-8"),
                    mode=0o640,
                ),
                call(
                    self.server.interfaces_filename,
                    interface["name"].encode("utf-8"),
                    mode=0o640,
                ),
            ],
        )
        on.assert_called_once_with()
        restart_service.assert_called_once_with(self.server.dhcp_service)
        self.assertEqual(
            dhcp._current_server_state[self.server.dhcp_service],
            dhcp.DHCPState(
                omapi_key,
                [failover_peers],
                [shared_network],
                [host],
                [interface],
                global_dhcp_snippets,
            ),
        )

    @inlineCallbacks
    def test_writes_config_and_calls_restart_when_non_host_state_diff(self):
        write_file = self.patch_sudo_write_file()
        restart_service = self.patch_restartService()

        failover_peers = make_failover_peer_config()
        shared_network = make_shared_network()
        [shared_network] = fix_shared_networks_failover(
            [shared_network], [failover_peers]
        )
        host = make_host()
        interface = make_interface()
        global_dhcp_snippets = make_global_dhcp_snippets()
        expected_config = factory.make_name("config")
        self.patch_get_config().return_value = expected_config

        dhcp_service = dhcp.service_monitor.getServiceByName(
            self.server.dhcp_service
        )
        on = self.patch_autospec(dhcp_service, "on")

        old_state = dhcp.DHCPState(
            factory.make_name("omapi_key"),
            [failover_peers],
            [shared_network],
            [host],
            [interface],
            global_dhcp_snippets,
        )
        dhcp._current_server_state[self.server.dhcp_service] = old_state

        omapi_key = factory.make_name("omapi_key")
        yield self.configure(
            omapi_key,
            [failover_peers],
            [shared_network],
            [host],
            [interface],
            global_dhcp_snippets,
        )

        write_file.assert_has_calls(
            [
                call(
                    self.server.config_filename,
                    expected_config.encode("utf-8"),
                    mode=0o640,
                ),
                call(
                    self.server.interfaces_filename,
                    interface["name"].encode("utf-8"),
                    mode=0o640,
                ),
            ]
        )
        on.assert_called_once_with()
        restart_service.assert_called_once_with(self.server.dhcp_service)
        self.assertEqual(
            dhcp._current_server_state[self.server.dhcp_service],
            dhcp.DHCPState(
                omapi_key,
                [failover_peers],
                [shared_network],
                [host],
                [interface],
                global_dhcp_snippets,
            ),
        )

    @inlineCallbacks
    def test_writes_config_and_calls_ensure_when_nothing_changed(self):
        write_file = self.patch_sudo_write_file()
        restart_service = self.patch_restartService()
        ensure_service = self.patch_ensureService()

        failover_peers = make_failover_peer_config()
        shared_network = make_shared_network()
        [shared_network] = fix_shared_networks_failover(
            [shared_network], [failover_peers]
        )
        host = make_host()
        interface = make_interface()
        dhcp_snippets = make_global_dhcp_snippets()
        expected_config = factory.make_name("config")
        self.patch_get_config().return_value = expected_config

        dhcp_service = dhcp.service_monitor.getServiceByName(
            self.server.dhcp_service
        )
        on = self.patch_autospec(dhcp_service, "on")

        omapi_key = factory.make_name("omapi_key")
        old_state = dhcp.DHCPState(
            omapi_key,
            [failover_peers],
            [shared_network],
            [host],
            [interface],
            dhcp_snippets,
        )
        dhcp._current_server_state[self.server.dhcp_service] = old_state

        yield self.configure(
            omapi_key,
            [failover_peers],
            [shared_network],
            [host],
            [interface],
            dhcp_snippets,
        )

        write_file.assert_has_calls(
            [
                call(
                    self.server.config_filename,
                    expected_config.encode("utf-8"),
                    mode=0o640,
                ),
                call(
                    self.server.interfaces_filename,
                    interface["name"].encode("utf-8"),
                    mode=0o640,
                ),
            ]
        )
        on.assert_called_once_with()
        restart_service.assert_not_called()
        ensure_service.assert_called_once_with(self.server.dhcp_service)
        self.assertEqual(
            dhcp._current_server_state[self.server.dhcp_service],
            dhcp.DHCPState(
                omapi_key,
                [failover_peers],
                [shared_network],
                [host],
                [interface],
                dhcp_snippets,
            ),
        )

    @inlineCallbacks
    def test_writes_config_and_doesnt_use_omapi_when_was_off(self):
        write_file = self.patch_sudo_write_file()
        get_service_state = self.patch_getServiceState()
        get_service_state.return_value = ServiceState(
            SERVICE_STATE.OFF, "dead"
        )
        restart_service = self.patch_restartService()
        ensure_service = self.patch_ensureService()
        update_hosts = self.patch_update_hosts()

        failover_peers = make_failover_peer_config()
        shared_network = make_shared_network()
        [shared_network] = fix_shared_networks_failover(
            [shared_network], [failover_peers]
        )
        host = make_host(dhcp_snippets=[])
        interface = make_interface()
        global_dhcp_snippets = make_global_dhcp_snippets()
        expected_config = factory.make_name("config")
        self.patch_get_config().return_value = expected_config

        dhcp_service = dhcp.service_monitor.getServiceByName(
            self.server.dhcp_service
        )
        on = self.patch_autospec(dhcp_service, "on")

        omapi_key = factory.make_name("omapi_key")
        old_host = make_host(dhcp_snippets=[])
        old_state = dhcp.DHCPState(
            omapi_key,
            [failover_peers],
            [shared_network],
            [old_host],
            [interface],
            global_dhcp_snippets,
        )
        dhcp._current_server_state[self.server.dhcp_service] = old_state

        yield self.configure(
            omapi_key,
            [failover_peers],
            [shared_network],
            [host],
            [interface],
            global_dhcp_snippets,
        )

        write_file.assert_has_calls(
            [
                call(
                    self.server.config_filename,
                    expected_config.encode("utf-8"),
                    mode=0o640,
                ),
                call(
                    self.server.interfaces_filename,
                    interface["name"].encode("utf-8"),
                    mode=0o640,
                ),
            ]
        )
        on.assert_called_once_with()
        get_service_state.assert_called_once_with(
            self.server.dhcp_service, now=True
        )
        restart_service.assert_not_called()
        ensure_service.assert_called_once_with(self.server.dhcp_service)
        update_hosts.assert_not_called()
        self.assertEqual(
            dhcp._current_server_state[self.server.dhcp_service],
            dhcp.DHCPState(
                omapi_key,
                [failover_peers],
                [shared_network],
                [host],
                [interface],
                global_dhcp_snippets,
            ),
        )

    @inlineCallbacks
    def test_writes_config_and_uses_omapi_to_update_hosts(self):
        write_file = self.patch_sudo_write_file()
        get_service_state = self.patch_getServiceState()
        get_service_state.return_value = ServiceState(
            SERVICE_STATE.ON, "running"
        )
        restart_service = self.patch_restartService()
        ensure_service = self.patch_ensureService()
        update_hosts = self.patch_update_hosts()

        failover_peers = make_failover_peer_config()
        shared_network = make_shared_network()
        [shared_network] = fix_shared_networks_failover(
            [shared_network], [failover_peers]
        )
        old_hosts = [make_host(dhcp_snippets=[]) for _ in range(3)]
        interface = make_interface()
        global_dhcp_snippets = make_global_dhcp_snippets()
        expected_config = factory.make_name("config")
        self.patch_get_config().return_value = expected_config

        dhcp_service = dhcp.service_monitor.getServiceByName(
            self.server.dhcp_service
        )
        on = self.patch_autospec(dhcp_service, "on")

        omapi_key = factory.make_name("omapi_key")
        old_state = dhcp.DHCPState(
            omapi_key,
            [failover_peers],
            [shared_network],
            old_hosts,
            [interface],
            global_dhcp_snippets,
        )
        dhcp._current_server_state[self.server.dhcp_service] = old_state

        new_hosts = copy.deepcopy(old_hosts)
        removed_host = new_hosts.pop()
        modified_host = new_hosts[0]
        modified_host["ip"] = factory.make_ip_address(
            ipv6=self.server.dhcp_service == "DHCPv6"
        )
        added_host = make_host(dhcp_snippets=[])
        new_hosts.append(added_host)

        yield self.configure(
            omapi_key,
            [failover_peers],
            [shared_network],
            new_hosts,
            [interface],
            global_dhcp_snippets,
        )

        write_file.assert_has_calls(
            [
                call(
                    self.server.config_filename,
                    expected_config.encode("utf-8"),
                    mode=0o640,
                ),
                call(
                    self.server.interfaces_filename,
                    interface["name"].encode("utf-8"),
                    mode=0o640,
                ),
            ]
        )
        on.assert_called_once_with()
        get_service_state.assert_called_once_with(
            self.server.dhcp_service, now=True
        )
        restart_service.assert_not_called()
        ensure_service.assert_called_once_with(self.server.dhcp_service)
        update_hosts.assert_called_once_with(
            ANY, [removed_host], [added_host], [modified_host]
        )
        self.assertEqual(
            dhcp._current_server_state[self.server.dhcp_service],
            dhcp.DHCPState(
                omapi_key,
                [failover_peers],
                [shared_network],
                new_hosts,
                [interface],
                global_dhcp_snippets,
            ),
        )

    @inlineCallbacks
    def test_writes_config_and_restarts_when_omapi_fails(self):
        write_file = self.patch_sudo_write_file()
        get_service_state = self.patch_getServiceState()
        get_service_state.return_value = ServiceState(
            SERVICE_STATE.ON, "running"
        )
        restart_service = self.patch_restartService()
        ensure_service = self.patch_ensureService()
        update_hosts = self.patch_update_hosts()
        update_hosts.side_effect = factory.make_exception()

        failover_peers = make_failover_peer_config()
        shared_network = make_shared_network()
        [shared_network] = fix_shared_networks_failover(
            [shared_network], [failover_peers]
        )
        old_hosts = [make_host(dhcp_snippets=[]) for _ in range(3)]
        interface = make_interface()
        global_dhcp_snippets = make_global_dhcp_snippets()
        expected_config = factory.make_name("config")
        self.patch_get_config().return_value = expected_config

        dhcp_service = dhcp.service_monitor.getServiceByName(
            self.server.dhcp_service
        )
        on = self.patch_autospec(dhcp_service, "on")

        omapi_key = factory.make_name("omapi_key")
        old_state = dhcp.DHCPState(
            omapi_key,
            [failover_peers],
            [shared_network],
            old_hosts,
            [interface],
            global_dhcp_snippets,
        )
        dhcp._current_server_state[self.server.dhcp_service] = old_state

        new_hosts = copy.deepcopy(old_hosts)
        removed_host = new_hosts.pop()
        modified_host = new_hosts[0]
        modified_host["ip"] = factory.make_ip_address(
            ipv6=self.server.dhcp_service == "DHCPv6"
        )
        added_host = make_host(dhcp_snippets=[])
        new_hosts.append(added_host)

        with FakeLogger("maas") as logger:
            yield self.configure(
                omapi_key,
                [failover_peers],
                [shared_network],
                new_hosts,
                [interface],
                global_dhcp_snippets,
            )

        write_file.assert_has_calls(
            [
                call(
                    self.server.config_filename,
                    expected_config.encode("utf-8"),
                    mode=0o640,
                ),
                call(
                    self.server.interfaces_filename,
                    interface["name"].encode("utf-8"),
                    mode=0o640,
                ),
            ]
        )
        on.assert_called_once_with()
        get_service_state.assert_called_once_with(
            self.server.dhcp_service, now=True
        )
        restart_service.assert_called_once_with(self.server.dhcp_service)
        ensure_service.assert_called_once_with(self.server.dhcp_service)
        update_hosts.assert_called_once_with(
            ANY, [removed_host], [added_host], [modified_host]
        )
        self.assertEqual(
            dhcp._current_server_state[self.server.dhcp_service],
            dhcp.DHCPState(
                omapi_key,
                [failover_peers],
                [shared_network],
                new_hosts,
                [interface],
                global_dhcp_snippets,
            ),
        )
        self.assertIn(
            (
                f"Failed to update all host maps. Restarting {self.server.descriptive_name} service "
                "to ensure host maps are in-sync."
            ),
            logger.output,
        )

    @inlineCallbacks
    def test_converts_failure_writing_file_to_CannotConfigureDHCP(self):
        self.patch_sudo_delete_file()
        self.patch_sudo_write_file().side_effect = ExternalProcessError(
            1, "sudo something"
        )
        self.patch_restartService()
        failover_peers = [make_failover_peer_config()]
        shared_networks = fix_shared_networks_failover(
            [make_shared_network()], failover_peers
        )
        with self.assertRaises(exceptions.CannotConfigureDHCP):
            yield self.configure(
                factory.make_name("key"),
                failover_peers,
                shared_networks,
                [make_host()],
                [make_interface()],
                make_global_dhcp_snippets(),
            )

    @inlineCallbacks
    def test_converts_dhcp_restart_failure_to_CannotConfigureDHCP(self):
        self.patch_sudo_write_file()
        self.patch_sudo_delete_file()
        self.patch_restartService().side_effect = ServiceActionError()
        failover_peers = [make_failover_peer_config()]
        shared_networks = fix_shared_networks_failover(
            [make_shared_network()], failover_peers
        )
        with self.assertRaises(exceptions.CannotConfigureDHCP):
            yield self.configure(
                factory.make_name("key"),
                failover_peers,
                shared_networks,
                [make_host()],
                [make_interface()],
                make_global_dhcp_snippets(),
            )

    @inlineCallbacks
    def test_converts_stop_dhcp_server_failure_to_CannotConfigureDHCP(self):
        self.patch_sudo_write_file()
        self.patch_sudo_delete_file()
        self.patch_ensureService().side_effect = ServiceActionError()
        with self.assertRaises(exceptions.CannotConfigureDHCP):
            yield self.configure(factory.make_name("key"), [], [], [], [], [])

    @inlineCallbacks
    def test_does_not_log_ServiceActionError(self):
        self.patch_sudo_write_file()
        self.patch_sudo_delete_file()
        self.patch_ensureService().side_effect = ServiceActionError()
        with FakeLogger("maas") as logger:
            with self.assertRaises(exceptions.CannotConfigureDHCP):
                yield self.configure(
                    factory.make_name("key"), [], [], [], [], []
                )
        self.assertEqual("", logger.output)

    @inlineCallbacks
    def test_does_log_other_exceptions(self):
        self.patch_sudo_write_file()
        self.patch_sudo_delete_file()
        self.patch_ensureService().side_effect = factory.make_exception(
            "DHCP is on strike today"
        )
        with FakeLogger("maas") as logger:
            with self.assertRaises(exceptions.CannotConfigureDHCP):
                yield self.configure(
                    factory.make_name("key"), [], [], [], [], []
                )
        self.assertRegex(
            logger.output,
            r"DHCPv[46] server failed to stop: DHCP is on strike today",
        )

    @inlineCallbacks
    def test_does_not_log_ServiceActionError_when_restarting(self):
        self.patch_sudo_write_file()
        self.patch_restartService().side_effect = ServiceActionError()
        failover_peers = [make_failover_peer_config()]
        shared_networks = fix_shared_networks_failover(
            [make_shared_network()], failover_peers
        )
        with FakeLogger("maas") as logger:
            with self.assertRaises(exceptions.CannotConfigureDHCP):
                yield self.configure(
                    factory.make_name("key"),
                    failover_peers,
                    shared_networks,
                    [make_host()],
                    [make_interface()],
                    make_global_dhcp_snippets(),
                )
        self.assertEqual("", logger.output)

    @inlineCallbacks
    def test_does_log_other_exceptions_when_restarting(self):
        self.patch_sudo_write_file()
        self.patch_restartService().side_effect = factory.make_exception(
            "DHCP is on strike today"
        )
        failover_peers = [make_failover_peer_config()]
        shared_networks = fix_shared_networks_failover(
            [make_shared_network()], failover_peers
        )
        with FakeLogger("maas") as logger:
            with self.assertRaises(exceptions.CannotConfigureDHCP):
                yield self.configure(
                    factory.make_name("key"),
                    failover_peers,
                    shared_networks,
                    [make_host()],
                    [make_interface()],
                    make_global_dhcp_snippets(),
                )
        self.assertRegex(
            logger.output,
            r"DHCPv[46] server failed to restart: DHCP is on strike today",
        )


class TestValidateDHCP(MAASTestCase):
    scenarios = (
        ("DHCPv4", {"server": dhcp.DHCPv4Server}),
        ("DHCPv6", {"server": dhcp.DHCPv6Server}),
    )

    def setUp(self):
        super().setUp()
        # Temporarily prevent hostname resolution when generating DHCP
        # configuration. This is tested elsewhere.
        self.useFixture(DHCPConfigNameResolutionDisabled())
        self.mock_call_and_check = self.patch(dhcp, "call_and_check")

    def validate(
        self,
        omapi_key,
        failover_peers,
        shared_networks,
        hosts,
        interfaces,
        dhcp_snippets,
    ):
        server = self.server(omapi_key)
        ret = dhcp.validate(
            server,
            failover_peers,
            shared_networks,
            hosts,
            interfaces,
            dhcp_snippets,
        )
        # Regression test for LP:1585814
        self.mock_call_and_check.assert_called_once_with(
            ["dhcpd", "-t", "-cf", "-6" if self.server.ipv6 else "-4", ANY]
        )
        return ret

    def test_good_config(self):
        omapi_key = factory.make_name("omapi_key")
        failover_peers = make_failover_peer_config()
        shared_network = make_shared_network()
        [shared_network] = fix_shared_networks_failover(
            [shared_network], [failover_peers]
        )
        host = make_host()
        interface = make_interface()
        global_dhcp_snippets = make_global_dhcp_snippets()

        self.assertEqual(
            None,
            self.validate(
                omapi_key,
                [failover_peers],
                [shared_network],
                [host],
                [interface],
                global_dhcp_snippets,
            ),
        )

    def test_bad_config(self):
        omapi_key = factory.make_name("omapi_key")
        failover_peers = make_failover_peer_config()
        shared_network = make_shared_network()
        [shared_network] = fix_shared_networks_failover(
            [shared_network], [failover_peers]
        )
        host = make_host()
        interface = make_interface()
        global_dhcp_snippets = make_global_dhcp_snippets()
        dhcpd_error = (
            "Internet Systems Consortium DHCP Server 4.3.3\n"
            "Copyright 2004-2015 Internet Systems Consortium.\n"
            "All rights reserved.\n"
            "For info, please visit https://www.isc.org/software/dhcp/\n"
            "/tmp/maas-dhcpd-z5c7hfzt line 14: semicolon expected.\n"
            "ignore \n"
            "^\n"
            "Configuration file errors encountered -- exiting\n"
            "\n"
            "If you think you have received this message due to a bug rather\n"
            "than a configuration issue please read the section on submitting"
            "\n"
            "bugs on either our web page at www.isc.org or in the README file"
            "\n"
            "before submitting a bug.  These pages explain the proper\n"
            "process and the information we find helpful for debugging..\n"
            "\n"
            "exiting."
        )
        self.mock_call_and_check.side_effect = ExternalProcessError(
            returncode=1, cmd=("dhcpd",), output=dhcpd_error
        )

        self.assertEqual(
            [
                {
                    "error": "semicolon expected.",
                    "line_num": 14,
                    "line": "ignore ",
                    "position": "^",
                }
            ],
            self.validate(
                omapi_key,
                [failover_peers],
                [shared_network],
                [host],
                [interface],
                global_dhcp_snippets,
            ),
        )
