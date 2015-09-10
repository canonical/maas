# Copyright 2014-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for the `osystems` module."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

from collections import (
    Counter,
    Iterator,
)

from maasserver.clusterrpc.osystems import (
    gen_all_known_operating_systems,
    get_os_release_title,
    get_preseed_data,
    validate_license_key,
    validate_license_key_for,
)
from maasserver.enum import (
    BOOT_RESOURCE_TYPE,
    PRESEED_TYPE,
)
from maasserver.rpc import getAllClients
from maasserver.rpc.testing.fixtures import RunningClusterRPCFixture
from maasserver.testing.architecture import make_usable_architecture
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from metadataserver.models import NodeKey
from provisioningserver.rpc.exceptions import NoSuchOperatingSystem
from testtools.matchers import (
    AfterPreprocessing,
    AllMatch,
    Equals,
    HasLength,
    IsInstance,
    Not,
)
from twisted.internet.defer import succeed


class TestGenAllKnownOperatingSystems(MAASServerTestCase):
    """Tests for `gen_all_known_operating_systems`."""

    def test_yields_oses_known_to_a_cluster(self):
        # The operating systems known to a single node are returned.
        factory.make_NodeGroup().accept()
        self.useFixture(RunningClusterRPCFixture())
        osystems = gen_all_known_operating_systems()
        self.assertIsInstance(osystems, Iterator)
        osystems = list(osystems)
        self.assertThat(osystems, Not(HasLength(0)))
        self.assertThat(osystems, AllMatch(IsInstance(dict)))

    def test_yields_oses_known_to_multiple_clusters(self):
        factory.make_NodeGroup().accept()
        factory.make_NodeGroup().accept()
        self.useFixture(RunningClusterRPCFixture())
        osystems = gen_all_known_operating_systems()
        self.assertIsInstance(osystems, Iterator)
        osystems = list(osystems)
        self.assertThat(osystems, Not(HasLength(0)))
        self.assertThat(osystems, AllMatch(IsInstance(dict)))

    def test_only_yields_os_once(self):
        # Duplicate OSes that exactly match are suppressed. Typically
        # every cluster will have several (or all) OSes in common.
        factory.make_NodeGroup().accept()
        factory.make_NodeGroup().accept()
        self.useFixture(RunningClusterRPCFixture())
        counter = Counter(
            osystem["name"] for osystem in
            gen_all_known_operating_systems())

        def get_count(item):
            name, count = item
            return count

        self.assertThat(
            counter.viewitems(), AllMatch(
                AfterPreprocessing(get_count, Equals(1))))

    def test_os_data_is_passed_through_unmolested(self):
        factory.make_NodeGroup().accept()
        self.useFixture(RunningClusterRPCFixture())
        example = {
            "osystems": [
                {
                    "name": factory.make_name("name"),
                    "foo": factory.make_name("foo"),
                    "bar": factory.make_name("bar"),
                },
            ],
        }
        for client in getAllClients():
            callRemote = self.patch(client._conn, "callRemote")
            callRemote.return_value = succeed(example)

        self.assertItemsEqual(
            example["osystems"], gen_all_known_operating_systems())

    def test_ignores_failures_when_talking_to_clusters(self):
        factory.make_NodeGroup().accept()
        factory.make_NodeGroup().accept()
        factory.make_NodeGroup().accept()
        self.useFixture(RunningClusterRPCFixture())

        clients = getAllClients()
        for index, client in enumerate(clients):
            callRemote = self.patch(client._conn, "callRemote")
            if index == 0:
                # The first client found returns dummy OS information which
                # includes the cluster's UUID (client.ident).
                example = {"osystems": [{"name": client.ident}]}
                callRemote.return_value = succeed(example)
            else:
                # All clients but the first raise an exception.
                callRemote.side_effect = ZeroDivisionError()

        # The only OS information to get through is that from the first. The
        # failures arising from communicating with the other clusters have all
        # been suppressed.
        self.assertItemsEqual(
            [{"name": clients[0].ident}],
            gen_all_known_operating_systems())

    def test_fixes_custom_osystem_release_titles(self):
        factory.make_NodeGroup().accept()
        self.useFixture(RunningClusterRPCFixture())

        releases = [factory.make_name("release") for _ in range(3)]
        os_releases = [
            {"name": release, "title": release}
            for release in releases
            ]
        for release in releases:
            factory.make_BootResource(
                rtype=BOOT_RESOURCE_TYPE.UPLOADED, name=release,
                architecture=make_usable_architecture(self),
                extra={"title": release.upper()})

        clients = getAllClients()
        for index, client in enumerate(clients):
            callRemote = self.patch(client._conn, "callRemote")
            example = {
                "osystems": [{"name": "custom", "releases": os_releases}]
                }
            callRemote.return_value = succeed(example)

        releases_with_titles = [
            {"name": release, "title": release.upper()}
            for release in releases
            ]
        self.assertItemsEqual(
            [{"name": "custom", "releases": releases_with_titles}],
            gen_all_known_operating_systems())


class TestGetOSReleaseTitle(MAASServerTestCase):
    """Tests for `get_os_release_title`."""

    def test_ignores_failures_when_talking_to_clusters(self):
        factory.make_NodeGroup().accept()
        factory.make_NodeGroup().accept()
        factory.make_NodeGroup().accept()
        self.useFixture(RunningClusterRPCFixture())

        title = factory.make_name('title')
        clients = getAllClients()
        for index, client in enumerate(clients):
            callRemote = self.patch(client._conn, "callRemote")
            if index == 0:
                # The first client found returns dummy title.
                example = {"title": title}
                callRemote.return_value = succeed(example)
            else:
                # All clients but the first raise an exception.
                callRemote.side_effect = ZeroDivisionError()

        # The only title to get through is that from the first. The
        # failures arising from communicating with the other clusters have all
        # been suppressed.
        self.assertEqual(
            title,
            get_os_release_title("bogus-os", "bogus-release"))

    def test_returns_None_if_title_is_blank(self):
        factory.make_NodeGroup().accept()
        self.useFixture(RunningClusterRPCFixture())

        clients = getAllClients()
        for index, client in enumerate(clients):
            callRemote = self.patch(client._conn, "callRemote")
            example = {"title": ""}
            callRemote.return_value = succeed(example)
        self.assertIsNone(get_os_release_title("bogus-os", "bogus-release"))


class TestGetPreseedData(MAASServerTestCase):
    """Tests for `get_preseed_data`."""

    def test_returns_preseed_data(self):
        # The Windows driver is known to provide custom preseed data.
        node = factory.make_Node(osystem="windows")
        node.nodegroup.accept()
        self.useFixture(RunningClusterRPCFixture())
        preseed_data = get_preseed_data(
            PRESEED_TYPE.COMMISSIONING, node,
            token=NodeKey.objects.get_token_for_node(node),
            metadata_url=factory.make_url())
        self.assertThat(preseed_data, IsInstance(dict))
        self.assertNotIn("data", preseed_data)
        self.assertThat(preseed_data, Not(HasLength(0)))

    def test_propagates_NotImplementedError(self):
        # The Windows driver is known to *not* provide custom preseed
        # data when using Curtin.
        node = factory.make_Node(osystem="windows")
        node.nodegroup.accept()
        self.useFixture(RunningClusterRPCFixture())
        self.assertRaises(
            NotImplementedError, get_preseed_data, PRESEED_TYPE.CURTIN,
            node, token=NodeKey.objects.get_token_for_node(node),
            metadata_url=factory.make_url())

    def test_propagates_NoSuchOperatingSystem(self):
        node = factory.make_Node(osystem=factory.make_name("foo"))
        node.nodegroup.accept()
        self.useFixture(RunningClusterRPCFixture())
        self.assertRaises(
            NoSuchOperatingSystem, get_preseed_data, PRESEED_TYPE.CURTIN,
            node, token=NodeKey.objects.get_token_for_node(node),
            metadata_url=factory.make_url())


class TestValidateLicenseKeyFor(MAASServerTestCase):
    """Tests for `validate_license_key_for`."""

    def test_propagates_NoSuchOperatingSystem(self):
        nodegroup = factory.make_NodeGroup()
        nodegroup.accept()
        osystem = factory.make_name('os')
        release = factory.make_name('release')
        key = factory.make_name('key')
        self.useFixture(RunningClusterRPCFixture())
        self.assertRaises(
            NoSuchOperatingSystem, validate_license_key_for, nodegroup,
            osystem, release, key)

    def test_returns_True(self):
        # The Windows driver is known accept a license key in the format of
        # 00000-00000-00000-00000-00000.
        nodegroup = factory.make_NodeGroup()
        nodegroup.accept()
        key = "00000-00000-00000-00000-00000"
        self.useFixture(RunningClusterRPCFixture())
        is_valid = validate_license_key_for(
            nodegroup, "windows", "win2012", key)
        self.assertTrue(is_valid)

    def test_returns_False(self):
        nodegroup = factory.make_NodeGroup()
        nodegroup.accept()
        key = factory.make_name('invalid-key')
        self.useFixture(RunningClusterRPCFixture())
        is_valid = validate_license_key_for(
            nodegroup, "windows", "win2012", key)
        self.assertFalse(is_valid)


class TestValidateLicenseKey(MAASServerTestCase):
    """Tests for `validate_license_key`."""

    def test_returns_True_with_one_cluster(self):
        # The Windows driver is known accept a license key in the format of
        # 00000-00000-00000-00000-00000.
        factory.make_NodeGroup().accept()
        key = "00000-00000-00000-00000-00000"
        self.useFixture(RunningClusterRPCFixture())
        is_valid = validate_license_key("windows", "win2012", key)
        self.assertTrue(is_valid)

    def test_returns_True_with_two_cluster(self):
        # The Windows driver is known accept a license key in the format of
        # 00000-00000-00000-00000-00000.
        factory.make_NodeGroup().accept()
        factory.make_NodeGroup().accept()
        key = "00000-00000-00000-00000-00000"
        self.useFixture(RunningClusterRPCFixture())
        is_valid = validate_license_key("windows", "win2012", key)
        self.assertTrue(is_valid)

    def test_returns_True_when_only_one_cluster_returns_True(self):
        # The Windows driver is known accept a license key in the format of
        # 00000-00000-00000-00000-00000.
        factory.make_NodeGroup().accept()
        factory.make_NodeGroup().accept()
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
            "windows", "win2012", factory.make_name("key"))
        self.assertTrue(is_valid)

    def test_returns_True_when_only_one_cluster_returns_True_others_fail(self):
        # The Windows driver is known accept a license key in the format of
        # 00000-00000-00000-00000-00000.
        factory.make_NodeGroup().accept()
        factory.make_NodeGroup().accept()
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
            "windows", "win2012", factory.make_name("key"))
        self.assertTrue(is_valid)

    def test_returns_False_with_one_cluster(self):
        factory.make_NodeGroup().accept()
        key = factory.make_name('invalid-key')
        self.useFixture(RunningClusterRPCFixture())
        is_valid = validate_license_key("windows", "win2012", key)
        self.assertFalse(is_valid)

    def test_returns_False_when_all_clusters_fail(self):
        factory.make_NodeGroup().accept()
        factory.make_NodeGroup().accept()
        self.useFixture(RunningClusterRPCFixture())

        clients = getAllClients()
        for index, client in enumerate(clients):
            # All clients raise an exception.
            callRemote = self.patch(client._conn, "callRemote")
            callRemote.side_effect = ZeroDivisionError()

        is_valid = validate_license_key(
            "windows", "win2012", factory.make_name('key'))
        self.assertFalse(is_valid)
