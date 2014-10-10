# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for :py:module:`~maasserver.rpc.cluster`."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

from copy import deepcopy

from django.core.exceptions import ValidationError
from fixtures import FakeLogger
from maasserver.enum import (
    NODEGROUP_STATUS,
    NODEGROUP_STATUS_CHOICES,
    )
from maasserver.rpc.clusters import (
    get_cluster_status,
    register_cluster,
    )
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from provisioningserver.rpc.exceptions import NoSuchCluster
from testtools.matchers import Equals


class TestGetClusterStatus(MAASServerTestCase):

    def test_returns_empty_list_when_cluster_does_not_exist(self):
        uuid = factory.make_UUID()
        self.assertRaises(NoSuchCluster, get_cluster_status, uuid)

    def test_returns_cluster_status(self):
        status = factory.pick_choice(NODEGROUP_STATUS_CHOICES)
        nodegroup = factory.make_NodeGroup(status=status)
        self.assertEqual(
            {b"status": status},
            get_cluster_status(nodegroup.uuid))


class TestRegister(MAASServerTestCase):

    def test__returns_preexisting_cluster(self):
        cluster = factory.make_NodeGroup()
        cluster_registered = register_cluster(
            cluster.uuid, factory.make_name("name"),
            factory.make_name("domain"), networks=[])
        self.assertEqual(cluster.uuid, cluster_registered.uuid)

    def test__updates_preexisting_cluster(self):
        cluster = factory.make_NodeGroup()
        # NodeGroup's field names are counterintuitive.
        new_name = factory.make_name(cluster.cluster_name)
        new_domain = factory.make_name(cluster.name)
        new_url = factory.make_parsed_url(
            scheme="http", params="", query="", fragment="")
        cluster_registered = register_cluster(
            cluster.uuid, new_name, new_domain, networks=[], url=new_url)
        self.expectThat(cluster.uuid, Equals(cluster_registered.uuid))
        self.expectThat(new_name, Equals(cluster_registered.cluster_name))
        self.expectThat(new_domain, Equals(cluster_registered.name))
        self.expectThat(new_url.geturl(), Equals(cluster_registered.maas_url))

    def test__automatically_accepts_cluster(self):
        cluster = register_cluster(
            factory.make_UUID(), factory.make_name("name"),
            factory.make_name("domain"), networks=[])
        self.assertEqual(NODEGROUP_STATUS.ACCEPTED, cluster.status)

    def test_name_domain_and_networks_are_optional(self):
        cluster = register_cluster(factory.make_UUID())
        self.assertEqual(NODEGROUP_STATUS.ACCEPTED, cluster.status)

    def get_cluster_networks(self, cluster):
        return [
            {"interface": ngi.interface, "ip": ngi.ip,
             "subnet_mask": ngi.subnet_mask}
            for ngi in cluster.nodegroupinterface_set.all()
        ]

    def test__accepts_a_list_of_networks(self):
        networks = [
            {"interface": "eth0", "ip": factory.make_ipv4_address(),
             "subnet_mask": "255.255.255.0"},
            {"interface": "eth1", "ip": factory.make_ipv6_address(),
             "subnet_mask": ""},
        ]
        cluster = register_cluster(
            factory.make_UUID(), networks=networks)
        networks_expected = deepcopy(networks)
        # For IPv6 networks the subnet mask must be blank when registering,
        # but is stored in full (always /64).
        networks_expected[1]["subnet_mask"] = "ffff:ffff:ffff:ffff::"
        networks_observed = self.get_cluster_networks(cluster)
        self.assertItemsEqual(networks_expected, networks_observed)

    def test__updates_networks_when_none_exist(self):
        networks = [
            {"interface": "eth0", "ip": factory.make_ipv4_address(),
             "subnet_mask": "255.255.255.255"},
            {"interface": "eth1", "ip": factory.make_ipv4_address(),
             "subnet_mask": "255.255.255.255"},
        ]
        cluster = register_cluster(factory.make_UUID())
        cluster = register_cluster(cluster.uuid, networks=networks)
        networks_observed = self.get_cluster_networks(cluster)
        self.assertItemsEqual(networks, networks_observed)

    def test__does_NOT_update_networks_when_some_exist(self):
        networks = [
            {"interface": "eth0", "ip": factory.make_ipv4_address(),
             "subnet_mask": "255.255.255.255"},
        ]
        cluster = register_cluster(
            factory.make_UUID(), networks=networks)
        networks += [
            {"interface": "eth1", "ip": factory.make_ipv4_address(),
             "subnet_mask": "255.255.255.255"},
        ]
        cluster = register_cluster(
            cluster.uuid, networks=networks)
        networks_expected = networks[:1]
        networks_observed = self.get_cluster_networks(cluster)
        self.assertItemsEqual(networks_expected, networks_observed)

    def test__accepts_a_url(self):
        url = factory.make_parsed_url(
            scheme="http", params="", query="", fragment="")
        cluster = register_cluster(factory.make_UUID(), url=url)
        self.assertEqual(url.geturl(), cluster.maas_url)

    def test__does_NOT_update_maas_url_if_localhost(self):
        cluster = factory.make_NodeGroup(
            maas_url=factory.make_simple_http_url())
        old_url = cluster.maas_url
        new_url = factory.make_parsed_url(
            scheme="http", netloc="localhost", params="", query="",
            fragment="")
        cluster_registered = register_cluster(cluster.uuid, url=new_url)
        self.assertEqual(old_url, cluster_registered.maas_url)

    def test__does_NOT_update_maas_url_if_none_provided(self):
        cluster = factory.make_NodeGroup(
            maas_url=factory.make_simple_http_url())
        old_url = cluster.maas_url
        cluster_registered = register_cluster(cluster.uuid, url=None)
        self.assertEqual(old_url, cluster_registered.maas_url)

    def test__raises_ValidationError_when_input_is_bad(self):
        error = self.assertRaises(
            ValidationError, register_cluster, factory.make_UUID(),
            name=("0123456789" * 11))
        self.assertEquals(
            [u'Ensure this value has at most 100 characters (it has 110).'],
            error.messages)

    def test__logs_creation_of_first_cluster_as_master(self):
        logger = self.useFixture(FakeLogger("maas"))
        cluster = register_cluster(factory.make_UUID())
        self.assertEqual(
            "New cluster registered as master: %s (%s)" % (
                cluster.cluster_name, cluster.uuid),
            logger.output.strip())

    def test__logs_creation_of_new_cluster(self):
        register_cluster(factory.make_UUID())  # Will become "master".
        logger = self.useFixture(FakeLogger("maas"))
        cluster = register_cluster(factory.make_UUID())
        self.assertEqual(
            "New cluster registered: %s (%s)" % (
                cluster.cluster_name, cluster.uuid),
            logger.output.strip())

    def test__logs_reappearance_of_existing_cluster(self):
        cluster = register_cluster(factory.make_UUID())
        logger = self.useFixture(FakeLogger("maas"))
        register_cluster(cluster.uuid)
        self.assertEqual(
            "Cluster registered: %s (%s)" % (
                cluster.cluster_name, cluster.uuid),
            logger.output.strip())
