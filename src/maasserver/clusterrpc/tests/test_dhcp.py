# Copyright 2014 Canonical Ltd.  This software is licensed under the
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
from maasserver.testing.factory import factory
from maastesting.matchers import MockCalledOnceWith
from maastesting.testcase import MAASTestCase
from mock import (
    Mock,
    sentinel,
    )
from provisioningserver.rpc.cluster import (
    CreateHostMaps,
    RemoveHostMaps,
    )
from testtools.matchers import (
    IsInstance,
    Matcher,
    MatchesAll,
    MatchesSetwise,
    MatchesStructure,
    )


class DummyClient:
    """A dummy client that's callable, and records the UUID."""

    def __init__(self, uuid):
        self.uuid = uuid

    def __call__(self):
        raise NotImplementedError()


class DummyClients(dict):
    """Lazily hand out `DummyClient` instances."""

    def __missing__(self, uuid):
        client = DummyClient(uuid)
        self[uuid] = client
        return client


class MatchesPartialCall(Matcher):

    def __init__(self, func, *args, **keywords):
        super(MatchesPartialCall, self).__init__()
        self.expected = partial(func, *args, **keywords)

    def match(self, observed):
        matcher = MatchesAll(
            IsInstance(partial),
            MatchesStructure.fromExample(
                self.expected, "func", "args", "keywords"),
            first_only=True,
        )
        return matcher.match(observed)


class TestGenCallsToCreateHostMaps(MAASTestCase):

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
            factory.make_node_group(
                status=NODEGROUP_STATUS.ACCEPTED,
                dhcp_key=factory.make_name("shared-key"))
            for _ in (1, 2)
        ]

        # Construct an example static mappings object that'll be passed
        # in to gen_calls_to_create_host_maps().
        static_mappings = {
            nodegroup: {
                factory.getRandomIPAddress(): factory.getRandomMACAddress()
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


class TestGenDynamicIPAddressesWithHostMaps(MAASTestCase):

    @staticmethod
    def make_leases_in_network(nodegroup, network, count=3):
        pick_address = factory.pick_ip_in_network
        leased_ips = set()
        for _ in xrange(count):
            ip_address = pick_address(network, but_not=leased_ips)
            yield factory.make_dhcp_lease(nodegroup=nodegroup, ip=ip_address)
            leased_ips.add(ip_address)

    def test__returns_nothing_when_there_are_no_static_mappings(self):
        static_mappings = {}
        calls = dhcp.gen_dynamic_ip_addresses_with_host_maps(static_mappings)
        self.assertThat(calls, IsInstance(Iterator))
        self.assertEqual([], list(calls))

    @staticmethod
    def make_nodegroup_and_interface():
        # Create and return an accepted nodegroup with a managed interface.
        nodegroup = factory.make_node_group(
            management=NODEGROUPINTERFACE_MANAGEMENT.DHCP,
            status=NODEGROUP_STATUS.ACCEPTED)
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
        addrs_expected = [
            (nodegroup, lease.ip)
            for lease in leases_without_static_range
        ]
        addrs = dhcp.gen_dynamic_ip_addresses_with_host_maps(static_mappings)
        self.assertThat(addrs, IsInstance(Iterator))
        self.assertItemsEqual(addrs_expected, addrs)

    def test__treats_undefined_static_range_as_zero_size_network(self):
        nodegroup, nodegroupiface = self.make_nodegroup_and_interface()
        nodegroupiface.static_ip_range_low = None
        nodegroupiface.static_ip_range_high = None

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
        addrs_expected = [
            (nodegroup, lease.ip)
            for lease in leases_without_static_range
        ]
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
        other_network = factory.getRandomNetwork(but_not={
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
        addrs_expected = [
            (nodegroup, lease.ip)
            for lease in leases_without_static_range
        ]
        addrs = dhcp.gen_dynamic_ip_addresses_with_host_maps(static_mappings)
        self.assertThat(addrs, IsInstance(Iterator))
        self.assertItemsEqual(addrs_expected, addrs)

    def test__only_returns_leases_outside_all_static_ranges_for_ng(self):
        nodegroup, _ = self.make_nodegroup_and_interface()

        # Add another 3 managed interfaces, for a total of 4.
        for _ in xrange(3):
            factory.make_node_group_interface(
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
        addrs_expected = [(nodegroup1, lease1.ip) for lease1 in leases1]
        addrs = dhcp.gen_dynamic_ip_addresses_with_host_maps(static_mappings)
        self.assertThat(addrs, IsInstance(Iterator))
        self.assertItemsEqual(addrs_expected, addrs)


class TestGenCallsToRemoveDynamicHostMaps(MAASTestCase):
    """Tests for `gen_calls_to_remove_dynamic_host_maps`."""

    def test__returns_zero_calls_when_there_are_no_static_mappings(self):
        self.assertItemsEqual(
            [], dhcp.gen_calls_to_remove_dynamic_host_maps(
                clients=DummyClients(), static_mappings={}))

    def test(self):
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
