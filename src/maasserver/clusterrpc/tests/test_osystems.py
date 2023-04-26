# Copyright 2014-2018 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for the `osystems` module."""


from collections import Counter
from collections.abc import Iterator

from testtools.matchers import (
    AfterPreprocessing,
    AllMatch,
    Equals,
    HasLength,
    IsInstance,
    Not,
)
from twisted.internet.defer import succeed

from maasserver.clusterrpc.osystems import (
    gen_all_known_operating_systems,
    get_preseed_data,
    validate_license_key,
)
from maasserver.enum import BOOT_RESOURCE_TYPE, PRESEED_TYPE
from maasserver.models import NodeKey
from maasserver.rpc import getAllClients
from maasserver.rpc.testing.fixtures import RunningClusterRPCFixture
from maasserver.testing.architecture import make_usable_architecture
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from provisioningserver.rpc.exceptions import NoSuchOperatingSystem


class TestGenAllKnownOperatingSystems(MAASServerTestCase):
    """Tests for `gen_all_known_operating_systems`."""

    def test_yields_oses_known_to_a_cluster(self):
        # The operating systems known to a single node are returned.
        factory.make_RackController()
        self.useFixture(RunningClusterRPCFixture())
        osystems = gen_all_known_operating_systems()
        self.assertIsInstance(osystems, Iterator)
        osystems = list(osystems)
        self.assertThat(osystems, Not(HasLength(0)))
        self.assertThat(osystems, AllMatch(IsInstance(dict)))

    def test_yields_oses_known_to_multiple_clusters(self):
        factory.make_RackController()
        factory.make_RackController()
        self.useFixture(RunningClusterRPCFixture())
        osystems = gen_all_known_operating_systems()
        self.assertIsInstance(osystems, Iterator)
        osystems = list(osystems)
        self.assertThat(osystems, Not(HasLength(0)))
        self.assertThat(osystems, AllMatch(IsInstance(dict)))

    def test_only_yields_os_once(self):
        # Duplicate OSes that exactly match are suppressed. Typically
        # every cluster will have several (or all) OSes in common.
        factory.make_RackController()
        factory.make_RackController()
        self.useFixture(RunningClusterRPCFixture())
        counter = Counter(
            osystem["name"] for osystem in gen_all_known_operating_systems()
        )

        def get_count(item):
            name, count = item
            return count

        self.assertThat(
            counter.items(), AllMatch(AfterPreprocessing(get_count, Equals(1)))
        )

    def test_os_data_is_passed_through_unmolested(self):
        factory.make_RackController()
        self.useFixture(RunningClusterRPCFixture())
        example = {
            "osystems": [
                {
                    "name": factory.make_name("name"),
                    "foo": factory.make_name("foo"),
                    "bar": factory.make_name("bar"),
                }
            ]
        }
        for client in getAllClients():
            callRemote = self.patch(client._conn, "callRemote")
            callRemote.return_value = succeed(example)

        self.assertEqual(
            example["osystems"], list(gen_all_known_operating_systems())
        )

    def test_ignores_failures_when_talking_to_clusters(self):
        factory.make_RackController()
        factory.make_RackController()
        factory.make_RackController()
        self.useFixture(RunningClusterRPCFixture())

        clients = getAllClients()
        for index, client in enumerate(clients):
            callRemote = self.patch(client._conn, "callRemote")
            if index == 0:
                # The first client found returns dummy OS information which
                # includes the rack controllers's system_id (client.ident).
                example = {"osystems": [{"name": client.ident}]}
                callRemote.return_value = succeed(example)
            else:
                # All clients but the first raise an exception.
                callRemote.side_effect = ZeroDivisionError()

        # The only OS information to get through is that from the first. The
        # failures arising from communicating with the other clusters have all
        # been suppressed.
        self.assertEqual(
            [{"name": clients[0].ident}],
            list(gen_all_known_operating_systems()),
        )

    def test_fixes_custom_osystem_release_titles(self):
        factory.make_RackController()
        self.useFixture(RunningClusterRPCFixture())

        releases = [factory.make_name("release") for _ in range(3)]
        os_releases = [
            {"name": release, "title": release} for release in releases
        ]
        for release in releases:
            factory.make_BootResource(
                rtype=BOOT_RESOURCE_TYPE.UPLOADED,
                name=release,
                architecture=make_usable_architecture(self),
                extra={"title": release.upper()},
            )

        clients = getAllClients()
        for index, client in enumerate(clients):
            callRemote = self.patch(client._conn, "callRemote")
            example = {
                "osystems": [{"name": "custom", "releases": os_releases}]
            }
            callRemote.return_value = succeed(example)

        releases_with_titles = [
            {"name": release, "title": release.upper()} for release in releases
        ]
        self.assertEqual(
            [{"name": "custom", "releases": releases_with_titles}],
            list(gen_all_known_operating_systems()),
        )


class TestGetPreseedData(MAASServerTestCase):
    """Tests for `get_preseed_data`."""

    def test_returns_preseed_data(self):
        # The Windows driver is known to provide custom preseed data.
        rack = factory.make_RackController()
        node = factory.make_Node(interface=True, osystem="windows")
        boot_interface = node.get_boot_interface()
        boot_interface.vlan.dhcp_on = True
        boot_interface.vlan.primary_rack = rack
        boot_interface.vlan.save()
        self.useFixture(RunningClusterRPCFixture())
        preseed_data = get_preseed_data(
            PRESEED_TYPE.COMMISSIONING,
            node,
            token=NodeKey.objects.get_token_for_node(node),
            metadata_url=factory.make_url(),
        )
        self.assertIsInstance(preseed_data, dict)
        self.assertNotIn("data", preseed_data)
        self.assertThat(preseed_data, Not(HasLength(0)))

    def test_propagates_NotImplementedError(self):
        # The Windows driver is known to *not* provide custom preseed
        # data when using Curtin.
        rack = factory.make_RackController()
        node = factory.make_Node(interface=True, osystem="windows")
        boot_interface = node.get_boot_interface()
        boot_interface.vlan.dhcp_on = True
        boot_interface.vlan.primary_rack = rack
        boot_interface.vlan.save()
        self.useFixture(RunningClusterRPCFixture())
        self.assertRaises(
            NotImplementedError,
            get_preseed_data,
            PRESEED_TYPE.CURTIN,
            node,
            token=NodeKey.objects.get_token_for_node(node),
            metadata_url=factory.make_url(),
        )

    def test_propagates_NoSuchOperatingSystem(self):
        rack = factory.make_RackController()
        node = factory.make_Node(
            interface=True, osystem=factory.make_name("foo")
        )
        boot_interface = node.get_boot_interface()
        boot_interface.vlan.dhcp_on = True
        boot_interface.vlan.primary_rack = rack
        boot_interface.vlan.save()
        self.useFixture(RunningClusterRPCFixture())
        self.assertRaises(
            NoSuchOperatingSystem,
            get_preseed_data,
            PRESEED_TYPE.CURTIN,
            node,
            token=NodeKey.objects.get_token_for_node(node),
            metadata_url=factory.make_url(),
        )


class TestValidateLicenseKey(MAASServerTestCase):
    """Tests for `validate_license_key`."""

    def test_returns_True_with_one_cluster(self):
        # The Windows driver is known accept a license key in the format of
        # 00000-00000-00000-00000-00000.
        factory.make_RackController()
        key = "00000-00000-00000-00000-00000"
        self.useFixture(RunningClusterRPCFixture())
        is_valid = validate_license_key("windows", "win2012", key)
        self.assertTrue(is_valid)

    def test_returns_True_with_two_cluster(self):
        # The Windows driver is known accept a license key in the format of
        # 00000-00000-00000-00000-00000.
        factory.make_RackController()
        factory.make_RackController()
        key = "00000-00000-00000-00000-00000"
        self.useFixture(RunningClusterRPCFixture())
        is_valid = validate_license_key("windows", "win2012", key)
        self.assertTrue(is_valid)

    def test_returns_True_when_only_one_cluster_returns_True(self):
        # The Windows driver is known accept a license key in the format of
        # 00000-00000-00000-00000-00000.
        factory.make_RackController()
        factory.make_RackController()
        self.useFixture(RunningClusterRPCFixture())

        clients = getAllClients()
        for index, client in enumerate(clients):
            callRemote = self.patch(client._conn, "callRemote")
            if index == 0:
                # The first client returns True.
                callRemote.return_value = succeed({"is_valid": True})
            else:
                # All clients but the first return False.
                callRemote.return_value = succeed({"is_valid": False})

        is_valid = validate_license_key(
            "windows", "win2012", factory.make_name("key")
        )
        self.assertTrue(is_valid)

    def test_returns_True_when_only_one_cluster_returns_True_others_fail(self):
        # The Windows driver is known accept a license key in the format of
        # 00000-00000-00000-00000-00000.
        factory.make_RackController()
        factory.make_RackController()
        self.useFixture(RunningClusterRPCFixture())

        clients = getAllClients()
        for index, client in enumerate(clients):
            callRemote = self.patch(client._conn, "callRemote")
            if index == 0:
                # The first client returns True.
                callRemote.return_value = succeed({"is_valid": True})
            else:
                # All clients but the first raise an exception.
                callRemote.side_effect = ZeroDivisionError()

        is_valid = validate_license_key(
            "windows", "win2012", factory.make_name("key")
        )
        self.assertTrue(is_valid)

    def test_returns_False_with_one_cluster(self):
        factory.make_RackController()
        key = factory.make_name("invalid-key")
        self.useFixture(RunningClusterRPCFixture())
        is_valid = validate_license_key("windows", "win2012", key)
        self.assertFalse(is_valid)

    def test_returns_False_when_all_clusters_fail(self):
        factory.make_RackController()
        factory.make_RackController()
        self.useFixture(RunningClusterRPCFixture())

        clients = getAllClients()
        for index, client in enumerate(clients):
            # All clients raise an exception.
            callRemote = self.patch(client._conn, "callRemote")
            callRemote.side_effect = ZeroDivisionError()

        is_valid = validate_license_key(
            "windows", "win2012", factory.make_name("key")
        )
        self.assertFalse(is_valid)
