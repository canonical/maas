# Copyright 2014-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for the `dhcp` module."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

from collections import Iterator
from functools import partial
from itertools import (
    chain,
    izip,
)

from maasserver.clusterrpc import dhcp
from maasserver.enum import (
    NODEGROUP_STATUS,
    NODEGROUPINTERFACE_MANAGEMENT,
)
from maasserver.fields import MAC
from maasserver.rpc import getClientFor
from maasserver.rpc.testing.doubles import DummyClients
from maasserver.rpc.testing.fixtures import (
    MockLiveRegionToClusterRPCFixture,
    MockRegionToClusterRPCFixture,
)
from maasserver.testing.eventloop import (
    RegionEventLoopFixture,
    RunningEventLoopFixture,
)
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maastesting.matchers import (
    MatchesPartialCall,
    MockCalledOnceWith,
    MockNotCalled,
)
from maastesting.testcase import MAASTestCase
from mock import (
    ANY,
    Mock,
    sentinel,
)
from provisioningserver.rpc.cluster import (
    CreateHostMaps,
    RemoveHostMaps,
)
from provisioningserver.utils.twisted import reactor_sync
from testtools.matchers import (
    AfterPreprocessing,
    AllMatch,
    HasLength,
    IsInstance,
    MatchesAll,
    MatchesPredicateWithParams,
    MatchesSetwise,
)
from twisted.internet import defer

# Matcher for a generator that yields nothing. In the context of
# `update_host_maps` (and `remove_host_maps`), this means success.
UpdateSucceeded = MatchesAll(
    IsInstance(Iterator), AfterPreprocessing(list, HasLength(0)),
    first_only=True)


# Matcher for testing Twisted Failure objects against a given exception.
FailedWith = MatchesPredicateWithParams(
    lambda failure, expected: failure.check(expected),
    "{0} does not represent a {1}", name="FailsWith")


class TestUpdateHostMaps(MAASServerTestCase):
    """Tests for `update_host_maps`."""

    @staticmethod
    def make_managed_node_group():
        return factory.make_NodeGroup(
            management=NODEGROUPINTERFACE_MANAGEMENT.DHCP,
            status=NODEGROUP_STATUS.ENABLED)

    def prepare_rpc(self):
        self.useFixture(RegionEventLoopFixture("rpc"))
        self.useFixture(RunningEventLoopFixture())
        nodegroup = self.make_managed_node_group()
        rpc_fixture = MockRegionToClusterRPCFixture()
        protocol, io = self.useFixture(rpc_fixture).makeCluster(
            nodegroup, CreateHostMaps, RemoveHostMaps)
        return nodegroup, protocol, io

    def prepare_live_rpc(self):
        self.useFixture(RegionEventLoopFixture("rpc"))
        self.useFixture(RunningEventLoopFixture())
        nodegroup = self.make_managed_node_group()
        rpc_fixture = MockLiveRegionToClusterRPCFixture()
        protocol = self.useFixture(rpc_fixture).makeCluster(
            nodegroup, CreateHostMaps, RemoveHostMaps)
        return nodegroup, protocol

    def test__does_nothing_when_there_are_no_host_maps(self):
        nodegroup, protocol, io = self.prepare_rpc()

        self.assertThat(
            dhcp.update_host_maps({}),
            UpdateSucceeded)

        # No IO was scheduled because no RPC calls were issued.
        with reactor_sync():
            self.assertFalse(io.pump())
            self.assertThat(protocol.CreateHostMaps, MockNotCalled())

    def patch_gen_calls_functions(self):
        gen_calls_to_remove_dynamic_host_maps = self.patch(
            dhcp, "gen_calls_to_remove_dynamic_host_maps")
        gen_calls_to_remove_dynamic_host_maps.return_value = []
        gen_calls_to_create_host_maps = self.patch(
            dhcp, "gen_calls_to_create_host_maps")
        gen_calls_to_create_host_maps.return_value = []

    @staticmethod
    def make_example_static_mappings(nodegroup):
        return {nodegroup: {sentinel.ip_address: sentinel.mac_address}}

    def test__stops_when_there_are_errors_removing_dynamic_leases(self):
        nodegroup, protocol, io = self.prepare_rpc()
        static_mappings = self.make_example_static_mappings(nodegroup)

        def goodbye():
            raise RuntimeError("Goodbye cruel world")

        self.patch_gen_calls_functions()
        dhcp.gen_calls_to_remove_dynamic_host_maps.return_value = [goodbye]

        self.assertThat(
            dhcp.update_host_maps(static_mappings),
            AfterPreprocessing(list, MatchesAll(
                HasLength(1), AllMatch(FailedWith(RuntimeError)))),
        )

        self.assertThat(
            dhcp.gen_calls_to_remove_dynamic_host_maps,
            MockCalledOnceWith(ANY, static_mappings))
        self.assertThat(
            dhcp.gen_calls_to_create_host_maps,
            MockNotCalled())

    def test__yields_only_failures_when_creating_host_maps(self):
        nodegroup, protocol, io = self.prepare_rpc()
        static_mappings = self.make_example_static_mappings(nodegroup)

        def goodbye():
            raise RuntimeError("Goodbye cruel world")

        self.patch_gen_calls_functions()
        dhcp.gen_calls_to_create_host_maps.return_value = [goodbye]

        self.assertThat(
            dhcp.update_host_maps(static_mappings),
            AfterPreprocessing(list, MatchesAll(
                HasLength(1), AllMatch(FailedWith(RuntimeError)))),
        )

        self.assertThat(
            dhcp.gen_calls_to_remove_dynamic_host_maps,
            MockCalledOnceWith(ANY, static_mappings))
        self.assertThat(
            dhcp.gen_calls_to_create_host_maps,
            MockCalledOnceWith(ANY, static_mappings))

    def test__yields_nothing_when_everything_is_okay(self):
        nodegroup, protocol, io = self.prepare_rpc()
        static_mappings = self.make_example_static_mappings(nodegroup)

        def hello():
            return "Hello there"

        self.patch_gen_calls_functions()
        dhcp.gen_calls_to_remove_dynamic_host_maps.return_value = [hello]
        dhcp.gen_calls_to_create_host_maps.return_value = [hello]

        self.assertThat(
            dhcp.update_host_maps(static_mappings),
            UpdateSucceeded)

        self.assertThat(
            dhcp.gen_calls_to_remove_dynamic_host_maps,
            MockCalledOnceWith(ANY, static_mappings))
        self.assertThat(
            dhcp.gen_calls_to_create_host_maps,
            MockCalledOnceWith(ANY, static_mappings))

    def test__passes_in_map_of_clients_to_gen_calls(self):
        nodegroup, protocol, io = self.prepare_rpc()
        static_mappings = self.make_example_static_mappings(nodegroup)

        self.patch_gen_calls_functions()

        self.assertThat(
            dhcp.update_host_maps(static_mappings),
            UpdateSucceeded)

        expected_clients = {
            nodegroup: getClientFor(nodegroup.uuid)
            for nodegroup in static_mappings
        }

        self.assertThat(
            dhcp.gen_calls_to_remove_dynamic_host_maps,
            MockCalledOnceWith(expected_clients, ANY))
        self.assertThat(
            dhcp.gen_calls_to_create_host_maps,
            MockCalledOnceWith(expected_clients, ANY))

    def test__end_to_nearly_end(self):
        nodegroup, protocol = self.prepare_live_rpc()
        nodegroup.dhcp_key = factory.make_name("dhcp-key")

        # Make both CreateHostMaps and RemoveHostMaps report success.
        protocol.CreateHostMaps.return_value = defer.succeed({})
        protocol.RemoveHostMaps.return_value = defer.succeed({})

        [nodegroupiface] = nodegroup.get_managed_interfaces()

        # Convenience functions to create random IP addresses. The `seen`
        # argument prevents collisions.
        def get_random_ip(source, seen=set()):
            ip_address = factory.pick_ip_in_network(source, but_not=seen)
            seen.add(ip_address)
            return ip_address
        get_random_static_ip = partial(
            get_random_ip, source=nodegroupiface.get_static_ip_range())
        get_random_dynamic_ip = partial(
            get_random_ip, source=nodegroupiface.get_dynamic_ip_range())

        # These are the new mappings that we want to create host maps for.
        # Calls will be made to add these.
        static_mappings = {
            nodegroup: {
                get_random_static_ip(): factory.make_mac_address(),
                get_random_static_ip(): factory.make_mac_address(),
            }
        }

        # These are preexisting leases with addresses in the dynamic range.
        # The host maps for these will be removed.
        leases_in_the_dynamic_range = {
            factory.make_DHCPLease(
                nodegroup, get_random_dynamic_ip(), MAC(mac_address))
            for nodegroup, mappings in static_mappings.viewitems()
            for _, mac_address in mappings.viewitems()
        }

        # Make the call we've all been waiting for.
        self.assertThat(
            dhcp.update_host_maps(static_mappings),
            UpdateSucceeded)

        # The host maps in the dynamic range were removed.
        self.assertThat(
            protocol.RemoveHostMaps, MockCalledOnceWith(
                ANY, ip_addresses=ANY, shared_key=nodegroup.dhcp_key))
        expected_ip_addresses = sum([
            [lease.ip, lease.mac.get_raw()]
            for lease in leases_in_the_dynamic_range], [])
        _, _, kwargs = protocol.RemoveHostMaps.mock_calls[0]
        observed_ip_addresses = kwargs["ip_addresses"]
        self.assertItemsEqual(expected_ip_addresses, observed_ip_addresses)

        # The new host maps were created.
        self.assertThat(
            protocol.CreateHostMaps, MockCalledOnceWith(
                ANY, mappings=ANY, shared_key=nodegroup.dhcp_key))
        expected_mappings = [
            {"ip_address": ip_address, "mac_address": mac_address}
            for ip_address, mac_address in
            static_mappings[nodegroup].viewitems()
        ]
        _, _, kwargs = protocol.CreateHostMaps.mock_calls[0]
        observed_mappings = kwargs["mappings"]
        self.assertItemsEqual(expected_mappings, observed_mappings)


class TestRemoveHostMaps(MAASServerTestCase):
    """Tests for `remove_host_maps`."""

    @staticmethod
    def make_managed_node_group():
        return factory.make_NodeGroup(
            management=NODEGROUPINTERFACE_MANAGEMENT.DHCP,
            status=NODEGROUP_STATUS.ENABLED)

    def prepare_rpc(self):
        self.useFixture(RegionEventLoopFixture("rpc"))
        self.useFixture(RunningEventLoopFixture())
        nodegroup = self.make_managed_node_group()
        rpc_fixture = self.useFixture(MockRegionToClusterRPCFixture())
        protocol, io = rpc_fixture.makeCluster(nodegroup, RemoveHostMaps)
        return nodegroup, protocol, io

    def prepare_live_rpc(self):
        self.useFixture(RegionEventLoopFixture("rpc"))
        self.useFixture(RunningEventLoopFixture())
        nodegroup = self.make_managed_node_group()
        rpc_fixture = MockLiveRegionToClusterRPCFixture()
        protocol = self.useFixture(rpc_fixture).makeCluster(
            nodegroup, RemoveHostMaps, RemoveHostMaps)
        return nodegroup, protocol

    def test__does_nothing_when_there_are_no_host_maps(self):
        nodegroup, protocol, io = self.prepare_rpc()

        self.assertThat(
            dhcp.remove_host_maps({}),
            UpdateSucceeded)

        # No IO was scheduled because no RPC calls were issued.
        with reactor_sync():
            self.assertFalse(io.pump())
            self.assertThat(protocol.RemoveHostMaps, MockNotCalled())

    @staticmethod
    def make_example_removal_mappings(nodegroup):
        return {nodegroup: [sentinel.ip1, sentinel.ip2]}

    def test__yields_only_failures_when_removing_host_maps(self):
        nodegroup, protocol, io = self.prepare_rpc()
        removal_mappings = self.make_example_removal_mappings(nodegroup)

        def goodbye():
            raise RuntimeError("Goodbye cruel world")

        self.patch_autospec(dhcp, "gen_calls_to_remove_host_maps")
        dhcp.gen_calls_to_remove_host_maps.return_value = [goodbye]

        self.assertThat(
            dhcp.remove_host_maps(removal_mappings),
            AfterPreprocessing(list, MatchesAll(
                HasLength(1), AllMatch(FailedWith(RuntimeError)))),
        )

        self.assertThat(
            dhcp.gen_calls_to_remove_host_maps,
            MockCalledOnceWith(ANY, removal_mappings))

    def test__yields_nothing_when_everything_is_okay(self):
        nodegroup, protocol, io = self.prepare_rpc()
        removal_mappings = self.make_example_removal_mappings(nodegroup)

        def hello():
            return "Hello there"

        self.patch_autospec(dhcp, "gen_calls_to_remove_host_maps")
        dhcp.gen_calls_to_remove_host_maps.return_value = [hello]

        self.assertThat(
            dhcp.remove_host_maps(removal_mappings),
            UpdateSucceeded)

        self.assertThat(
            dhcp.gen_calls_to_remove_host_maps,
            MockCalledOnceWith(ANY, removal_mappings))

    def test__passes_in_map_of_clients_to_gen_call(self):
        nodegroup, protocol, io = self.prepare_rpc()
        removal_mappings = self.make_example_removal_mappings(nodegroup)

        self.patch_autospec(dhcp, "gen_calls_to_remove_host_maps")
        dhcp.gen_calls_to_remove_host_maps.return_value = []

        self.assertThat(
            dhcp.remove_host_maps(removal_mappings),
            UpdateSucceeded)

        expected_clients = {
            nodegroup: getClientFor(nodegroup.uuid)
            for nodegroup in removal_mappings
        }
        self.assertThat(
            dhcp.gen_calls_to_remove_host_maps,
            MockCalledOnceWith(expected_clients, ANY))

    def test__end_to_nearly_end(self):
        nodegroup, protocol = self.prepare_live_rpc()
        nodegroup.dhcp_key = factory.make_name("dhcp-key")

        # Make RemoveHostMaps report success.
        protocol.RemoveHostMaps.return_value = defer.succeed({})

        [nodegroupiface] = nodegroup.get_managed_interfaces()

        # Convenience functions to create random IP addresses. The `seen`
        # argument prevents collisions.
        def get_random_ip(source, seen=set()):
            ip_address = factory.pick_ip_in_network(source, but_not=seen)
            seen.add(ip_address)
            return ip_address
        get_random_removal_ip = partial(
            get_random_ip, source=nodegroupiface.get_static_ip_range())

        # These are the new mappings that we want to create host maps for.
        # Calls will be made to add these.
        removal_mappings = {
            nodegroup: [
                get_random_removal_ip(),
                get_random_removal_ip(),
            ]
        }

        # Make the call we've all been waiting for.
        self.assertThat(
            dhcp.remove_host_maps(removal_mappings),
            UpdateSucceeded)

        # The host maps in the dynamic range were removed.
        self.assertThat(
            protocol.RemoveHostMaps, MockCalledOnceWith(
                ANY, ip_addresses=ANY, shared_key=nodegroup.dhcp_key))
        expected_ip_addresses = removal_mappings[nodegroup]
        _, _, kwargs = protocol.RemoveHostMaps.mock_calls[0]
        observed_ip_addresses = kwargs["ip_addresses"]
        self.assertItemsEqual(expected_ip_addresses, observed_ip_addresses)


class TestGenCallsToCreateHostMaps(MAASServerTestCase):

    def test__returns_zero_calls_when_there_are_no_static_mappings(self):
        clients = DummyClients()
        static_mappings = {}
        calls = dhcp.gen_calls_to_create_host_maps(clients, static_mappings)
        self.assertThat(calls, IsInstance(Iterator))
        self.assertEqual([], list(calls))
        # No clients were used either.
        self.assertEqual({}, clients)

    def test__returns_calls_for_each_mapping(self):
        clients = DummyClients()

        # Use a couple of nodegroups. gen_calls_to_create_host_maps()
        # will return a call for each of these, because each must be
        # sent mappings via a different client.
        nodegroups = [
            factory.make_NodeGroup(
                status=NODEGROUP_STATUS.ENABLED,
                dhcp_key=factory.make_name("shared-key"))
            for _ in (1, 2)
        ]

        # Construct an example static mappings object that'll be passed
        # in to gen_calls_to_create_host_maps().
        static_mappings = {
            nodegroup: {
                factory.make_ipv4_address(): factory.make_mac_address()
                for _ in xrange(3)
            }
            for nodegroup in nodegroups
        }

        calls = dhcp.gen_calls_to_create_host_maps(clients, static_mappings)
        self.assertThat(calls, IsInstance(Iterator))
        self.assertThat(
            calls, MatchesSetwise(*(
                # There is a call for each nodegroup, using a client
                # specific to that nodegroup. Each calls CreateHostMaps
                # with a "mappings" and "shared_key" argument.
                MatchesPartialCall(
                    clients[nodegroup], CreateHostMaps,
                    shared_key=nodegroup.dhcp_key,
                    mappings=[
                        {"ip_address": ip_address, "mac_address": mac_address}
                        for ip_address, mac_address in mappings.viewitems()
                    ],
                )
                for nodegroup, mappings in static_mappings.viewitems()
            ))
        )

    def test__skips_IPv6_mappings(self):
        clients = DummyClients()
        nodegroup = factory.make_NodeGroup(
            status=NODEGROUP_STATUS.ENABLED,
            dhcp_key=factory.make_name("key"))

        static_mapping = {
            nodegroup: {
                factory.make_ipv6_address(): factory.make_mac_address()
            }
        }

        calls = dhcp.gen_calls_to_create_host_maps(clients, static_mapping)
        self.assertThat(calls, IsInstance(Iterator))
        calls = list(calls)
        self.assertThat(calls, HasLength(1))
        [call] = calls
        # The mappings are empty.
        self.assertThat(
            call,
            MatchesPartialCall(
                clients[nodegroup], CreateHostMaps, shared_key=ANY,
                mappings=[]))


class TestGenDynamicIPAddressesWithHostMaps(MAASServerTestCase):

    @staticmethod
    def make_leases_in_network(nodegroup, network, count=3):
        pick_address = factory.pick_ip_in_network
        leased_ips = set()
        for _ in xrange(count):
            ip_address = pick_address(network, but_not=leased_ips)
            yield factory.make_DHCPLease(nodegroup=nodegroup, ip=ip_address)
            leased_ips.add(ip_address)

    def test__returns_nothing_when_there_are_no_static_mappings(self):
        static_mappings = {}
        calls = dhcp.gen_dynamic_ip_addresses_with_host_maps(static_mappings)
        self.assertThat(calls, IsInstance(Iterator))
        self.assertEqual([], list(calls))

    @staticmethod
    def make_nodegroup_and_interface():
        # Create and return an accepted nodegroup with a managed interface.
        nodegroup = factory.make_NodeGroup(
            management=NODEGROUPINTERFACE_MANAGEMENT.DHCP,
            status=NODEGROUP_STATUS.ENABLED)
        [nodegroupiface] = nodegroup.get_managed_interfaces()
        return nodegroup, nodegroupiface

    @staticmethod
    def make_static_mappings(nodegroup, *leases):
        # Construct a `static_mappings` argument.
        return {
            nodegroup: {
                lease.ip: lease.mac.get_raw()
                for lease in chain.from_iterable(leases)
            }
        }

    def test__returns_leases_that_are_outside_static_range(self):
        nodegroup, nodegroupiface = self.make_nodegroup_and_interface()

        # Generate some leases within and without the _static_ range of the
        # above nodegroup's only interface.
        leases_within_static_range = list(self.make_leases_in_network(
            nodegroup, nodegroupiface.get_static_ip_range()))
        leases_without_static_range = list(self.make_leases_in_network(
            nodegroup, nodegroupiface.get_dynamic_ip_range()))

        # This is our input into the gen_dynamic_ip_addresses_with_host_maps
        # function. We pass in data about all the leases we've created.
        static_mappings = self.make_static_mappings(
            nodegroup, leases_within_static_range,
            leases_without_static_range)

        # Only the leases that fall outside of the static range are in
        # gen_dynamic_ip_addresses_with_host_maps's output.
        addrs_expected = sum([
            [
                (nodegroup, lease.ip),
                (nodegroup, lease.mac.get_raw())
            ]
            for lease in leases_without_static_range], [])
        addrs = dhcp.gen_dynamic_ip_addresses_with_host_maps(static_mappings)
        self.assertThat(addrs, IsInstance(Iterator))
        self.assertItemsEqual(addrs_expected, addrs)

    def test__treats_undefined_static_range_as_zero_size_network(self):
        nodegroup, nodegroupiface = self.make_nodegroup_and_interface()
        nodegroupiface.static_ip_range_low = None
        nodegroupiface.static_ip_range_high = None
        nodegroupiface.save()

        # Generate some leases within and without the _static_ range of the
        # above nodegroup's only interface.
        leases_without_static_range = list(self.make_leases_in_network(
            nodegroup, nodegroupiface.get_dynamic_ip_range()))

        # This is our input into the gen_dynamic_ip_addresses_with_host_maps
        # function. We pass in data about all the leases we've created.
        static_mappings = self.make_static_mappings(
            nodegroup, leases_without_static_range)

        # All leases fall outside of the static range -- because there isn't
        # one -- so gen_dynamic_ip_addresses_with_host_maps returns them all.
        addrs_expected = sum([
            [
                (nodegroup, lease.ip),
                (nodegroup, lease.mac.get_raw())
            ]
            for lease in leases_without_static_range], [])
        addrs = dhcp.gen_dynamic_ip_addresses_with_host_maps(static_mappings)
        self.assertThat(addrs, IsInstance(Iterator))
        self.assertItemsEqual(addrs_expected, addrs)

    def test__only_considers_macs_when_searching_for_leases(self):
        nodegroup, nodegroupiface = self.make_nodegroup_and_interface()

        # Generate some leases within and without the _static_ range of the
        # above nodegroup's only interface.
        leases_without_static_range = list(self.make_leases_in_network(
            nodegroup, nodegroupiface.get_dynamic_ip_range()))
        # Change the IP addresses for these leases to be in another network.
        other_network = factory.make_ipv4_network(but_not={
            nodegroupiface.get_dynamic_ip_range(),
            nodegroupiface.get_static_ip_range()})
        for lease in leases_without_static_range:
            lease.ip = factory.pick_ip_in_network(other_network, but_not={
                lease.ip for lease in leases_without_static_range})
            lease.save()  # Django doesn't flush for some reason.

        # This is our input into the gen_dynamic_ip_addresses_with_host_maps
        # function. We pass in data about all the leases we've created.
        static_mappings = self.make_static_mappings(
            nodegroup, leases_without_static_range)

        # All leases fall outside of the static range so they're all returned
        # even though they don't fall within any managed range of this
        # nodegroup. The assumption is that at some point in the past this
        # lease was within a range attributed to this nodegroup, and it thus
        # has the authority to revoke it.
        addrs_expected = sum([
            [
                (nodegroup, lease.ip),
                (nodegroup, lease.mac.get_raw())
            ]
            for lease in leases_without_static_range], [])

        addrs = dhcp.gen_dynamic_ip_addresses_with_host_maps(static_mappings)
        self.assertThat(addrs, IsInstance(Iterator))
        self.assertItemsEqual(addrs_expected, addrs)

    def test__only_returns_leases_outside_all_static_ranges_for_ng(self):
        nodegroup, _ = self.make_nodegroup_and_interface()

        # Add another 3 managed interfaces, for a total of 4.
        for _ in xrange(3):
            factory.make_NodeGroupInterface(
                management=NODEGROUPINTERFACE_MANAGEMENT.DHCP,
                nodegroup=nodegroup)

        # Create leases in each interface's static range
        leases = [
            lease
            for nodegroupiface in nodegroup.get_managed_interfaces()
            for lease in self.make_leases_in_network(
                nodegroup, nodegroupiface.get_static_ip_range())
        ]

        # This is our input into the gen_dynamic_ip_addresses_with_host_maps
        # function. We pass in data about all the leases we've created.
        static_mappings = self.make_static_mappings(nodegroup, leases)

        # None of the leases created fall out of every static range, so none
        # are in gen_dynamic_ip_addresses_with_host_maps's output.
        addrs = dhcp.gen_dynamic_ip_addresses_with_host_maps(static_mappings)
        self.assertThat(addrs, IsInstance(Iterator))
        self.assertItemsEqual([], addrs)

    def test__only_considers_leases_for_the_given_nodegroup(self):
        nodegroup1, nodegroupiface1 = self.make_nodegroup_and_interface()
        nodegroup2, nodegroupiface2 = self.make_nodegroup_and_interface()

        # Create leases for both nodegroups' dynamic ranges.
        leases1 = list(self.make_leases_in_network(
            nodegroup1, nodegroupiface1.get_dynamic_ip_range()))
        leases2 = list(self.make_leases_in_network(
            nodegroup2, nodegroupiface2.get_dynamic_ip_range()))

        # Mangle the leases for the second nodegroup to have the same MAC
        # addresses as those for the first nodegroup.
        for lease1, lease2 in izip(leases1, leases2):
            lease2.mac = lease1.mac
            lease2.save()

        # Pass the static mappings for only the first nodegroup.
        static_mappings = self.make_static_mappings(nodegroup1, leases1)

        # Only the leases associated with the first nodegroup are returned.
        addrs_expected = sum([
            [
                (nodegroup1, lease1.ip),
                (nodegroup1, lease1.mac.get_raw())
            ]
            for lease1 in leases1], [])
        addrs = dhcp.gen_dynamic_ip_addresses_with_host_maps(static_mappings)
        self.assertThat(addrs, IsInstance(Iterator))
        self.assertItemsEqual(addrs_expected, addrs)


class TestGenCallsToRemoveDynamicHostMaps(MAASTestCase):
    """Tests for `gen_calls_to_remove_dynamic_host_maps`."""

    def test__returns_zero_calls_when_there_are_no_static_mappings(self):
        self.assertItemsEqual(
            [], dhcp.gen_calls_to_remove_dynamic_host_maps(
                clients=DummyClients(), static_mappings={}))

    def test__generates_correct_calls(self):
        clients = DummyClients()

        nodegroup_alice = Mock(name="Alice", dhcp_key=sentinel.alice_key)
        nodegroup_bob = Mock(name="Bob", dhcp_key=sentinel.bob_key)

        # Patch out gen_dynamic_ip_addresses_with_host_maps to return some
        # pre-canned data. We're interested in the transformation that
        # gen_calls_to_remove_dynamic_host_maps does on this data.
        gen_dynamics = self.patch(
            dhcp, "gen_dynamic_ip_addresses_with_host_maps")
        gen_dynamics.return_value = [
            (nodegroup_alice, sentinel.alice_ip_1),
            (nodegroup_bob, sentinel.bob_ip_1),
            (nodegroup_bob, sentinel.bob_ip_2),
        ]

        calls = dhcp.gen_calls_to_remove_dynamic_host_maps(
            clients=clients, static_mappings=sentinel.static_mappings)
        self.assertThat(calls, IsInstance(Iterator))
        self.assertThat(
            calls, MatchesSetwise(*(
                # There is a call for each nodegroup, using a client
                # specific to that nodegroup. Each calls RemoveHostMaps
                # with "ip_addresses" and "shared_key" arguments.
                MatchesPartialCall(
                    clients[nodegroup_alice], RemoveHostMaps,
                    ip_addresses={sentinel.alice_ip_1},
                    shared_key=sentinel.alice_key,
                ),
                MatchesPartialCall(
                    clients[nodegroup_bob], RemoveHostMaps,
                    ip_addresses={sentinel.bob_ip_1, sentinel.bob_ip_2},
                    shared_key=sentinel.bob_key,
                ),
            ))
        )
        # The call was made to gen_dynamic_ip_addresses_with_host_maps with
        # the given static_mappings object.
        self.assertThat(
            gen_dynamics, MockCalledOnceWith(sentinel.static_mappings))


class TestGenCallsToRemoveHostMaps(MAASTestCase):

    def test__returns_zero_calls_when_there_are_no_removal_mappings(self):
        self.assertItemsEqual(
            [], dhcp.gen_calls_to_remove_host_maps(
                clients=DummyClients(), removal_mappings={}))

    def test__generates_correct_calls(self):
        clients = DummyClients()

        nodegroup_alice = Mock(name="Alice", dhcp_key=sentinel.alice_key)
        nodegroup_bob = Mock(name="Bob", dhcp_key=sentinel.bob_key)

        removal_mappings = {
            nodegroup: [
                factory.make_ipv4_address(),
                factory.make_ipv6_address(),
            ]
            for nodegroup in (nodegroup_alice, nodegroup_bob)
        }

        calls = dhcp.gen_calls_to_remove_host_maps(
            clients=clients, removal_mappings=removal_mappings)
        self.assertThat(calls, IsInstance(Iterator))
        self.assertThat(
            calls, MatchesSetwise(*(
                # There is a call for each nodegroup, using a client
                # specific to that nodegroup. Each calls RemoveHostMaps
                # with "ip_addresses" and "shared_key" arguments.
                MatchesPartialCall(
                    clients[nodegroup_alice], RemoveHostMaps,
                    ip_addresses=removal_mappings[nodegroup_alice],
                    shared_key=sentinel.alice_key,
                ),
                MatchesPartialCall(
                    clients[nodegroup_bob], RemoveHostMaps,
                    ip_addresses=removal_mappings[nodegroup_bob],
                    shared_key=sentinel.bob_key,
                ),
            ))
        )
