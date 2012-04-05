# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `maasserver.provisioning`."""

from __future__ import (
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = []

from abc import ABCMeta
from xmlrpclib import Fault

from django.conf import settings
from maasserver import provisioning
from maasserver.exceptions import MAASAPIException
from maasserver.models import (
    ARCHITECTURE,
    Config,
    Node,
    NODE_AFTER_COMMISSIONING_ACTION,
    NODE_STATUS,
    NODE_STATUS_CHOICES,
    )
from maasserver.provisioning import (
    compose_preseed,
    get_metadata_server_url,
    name_arch_in_cobbler_style,
    present_user_friendly_fault,
    PRESENTATIONS,
    select_profile_for_node,
    )
from maasserver.testing.enum import map_enum
from maasserver.testing.factory import factory
from maasserver.testing.testcase import TestCase
from metadataserver.models import NodeKey
from provisioningserver.enum import (
    POWER_TYPE,
    PSERV_FAULT,
    )
from provisioningserver.testing.factory import ProvisioningFakeFactory
from testtools.deferredruntest import AsynchronousDeferredRunTest
from testtools.matchers import KeysEqual
from testtools.testcase import ExpectedException
from twisted.internet.defer import inlineCallbacks
import yaml


class ProvisioningTests:
    """Tests for the Provisioning API as maasserver sees it."""

    __metaclass__ = ABCMeta

    # This must be set to the provisioning server API proxy to test against.
    papi = None

    def make_node_without_saving(self, arch=ARCHITECTURE.i386):
        """Create a Node, but don't save it to the database."""
        system_id = "node-%s" % factory.getRandomString()
        return Node(
            system_id=system_id, hostname=factory.getRandomString(),
            status=NODE_STATUS.DEFAULT_STATUS, after_commissioning_action=(
                NODE_AFTER_COMMISSIONING_ACTION.DEFAULT),
            architecture=arch)

    def test_name_arch_in_cobbler_style_converts_architecture_names(self):
        self.assertSequenceEqual(
            ['i386', 'i386', 'x86_64', 'x86_64'],
            map(
                name_arch_in_cobbler_style,
                ['i386', 'i686', 'amd64', 'x86_64']))

    def test_name_arch_in_cobbler_works_for_both_bytes_and_unicode(self):
        self.assertEqual(
            name_arch_in_cobbler_style(u'amd64'),
            name_arch_in_cobbler_style(b'amd64'))

    def test_name_arch_in_cobbler_returns_unicode(self):
        self.assertIsInstance(name_arch_in_cobbler_style(b'amd64'), unicode)

    @inlineCallbacks
    def test_select_profile_for_node_ignores_previously_chosen_profile(self):
        node = factory.make_node(architecture='i386')
        profile = yield self.add_profile(self.papi)
        yield self.papi.modify_nodes({node.system_id: {'profile': profile}})
        self.assertEqual(
            'maas-precise-i386', select_profile_for_node(node))

    def test_select_profile_for_node_selects_Precise_and_right_arch(self):
        nodes = {
            arch: self.make_node_without_saving(arch=arch)
            for arch in map_enum(ARCHITECTURE).values()}
        self.assertItemsEqual([
                'maas-precise-%s' % name_arch_in_cobbler_style(arch)
                for arch in nodes.keys()],
            [
                select_profile_for_node(node)
                for node in nodes.values()])

    def test_select_profile_for_node_converts_architecture_name(self):
        node = factory.make_node(architecture='amd64')
        profile = select_profile_for_node(node)
        self.assertNotIn('amd64', profile)
        self.assertIn('x86_64', profile)

    def test_select_profile_for_node_works_for_commissioning(self):
        # A special profile is chosen for nodes in the commissioning
        # state.
        arch = ARCHITECTURE.i386
        node = factory.make_node(
            status=NODE_STATUS.COMMISSIONING, architecture=arch)
        profile = select_profile_for_node(node)
        self.assertEqual('maas-precise-%s-commissioning' % arch, profile)

    def test_provision_post_save_Node_create(self):
        # The handler for Node's post-save signal registers the node in
        # its current state with the provisioning server.
        node = factory.make_node(architecture=ARCHITECTURE.i386)
        provisioning.provision_post_save_Node(
            sender=Node, instance=node, created=True)
        system_id = node.system_id
        pserv_node = self.papi.get_nodes_by_name([system_id])[system_id]
        self.assertEqual("maas-precise-i386", pserv_node["profile"])

    def test_provision_post_save_Node_checks_for_missing_profile(self):
        # If the required profile for a node is missing, MAAS reports
        # that the maas-import-isos script may need running.

        def raise_missing_profile(*args, **kwargs):
            raise Fault(PSERV_FAULT.NO_SUCH_PROFILE, "Unknown profile.")

        self.papi.patch('add_node', raise_missing_profile)
        with ExpectedException(MAASAPIException):
            node = factory.make_node(architecture='amd32k')
            provisioning.provision_post_save_Node(
                sender=Node, instance=node, created=True)

    def test_provision_post_save_Node_returns_other_pserv_faults(self):

        def raise_fault(*args, **kwargs):
            raise Fault(PSERV_FAULT.NO_COBBLER, factory.getRandomString())

        self.papi.patch('add_node', raise_fault)
        with ExpectedException(MAASAPIException):
            node = factory.make_node(architecture='amd32k')
            provisioning.provision_post_save_Node(
                sender=Node, instance=node, created=True)

    def test_provision_post_save_Node_registers_effective_power_type(self):
        power_types = list(map_enum(POWER_TYPE).values())
        nodes = {
            power_type: factory.make_node(power_type=power_type)
            for power_type in power_types}
        effective_power_types = {
            power_type: node.get_effective_power_type()
            for power_type, node in nodes.items()}
        pserv_nodes = self.papi.get_nodes_by_name(
            node.system_id for node in nodes.values())
        pserv_power_types = {
            power_type: pserv_nodes[node.system_id]["power_type"]
            for power_type, node in nodes.items()}
        self.assertEqual(effective_power_types, pserv_power_types)

    def test_provision_post_save_MACAddress_create(self):
        # Creating and saving a MACAddress updates the Node with which it's
        # associated.
        node_model = factory.make_node(system_id="frank")
        node_model.add_mac_address("12:34:56:78:90:12")
        node = self.papi.get_nodes_by_name(["frank"])["frank"]
        self.assertEqual(["12:34:56:78:90:12"], node["mac_addresses"])

    def test_provision_post_save_Node_update(self):
        # Saving an existing node does not change the profile or distro
        # associated with it.
        node_model = factory.make_node(system_id="frank")
        provisioning.provision_post_save_Node(
            sender=Node, instance=node_model, created=True)
        # Record the current profile name.
        node = self.papi.get_nodes_by_name(["frank"])["frank"]
        profile_name1 = node["profile"]
        # Update the model node.
        provisioning.provision_post_save_Node(
            sender=Node, instance=node_model, created=False)
        # The profile name is unchanged.
        node = self.papi.get_nodes_by_name(["frank"])["frank"]
        profile_name2 = node["profile"]
        self.assertEqual(profile_name1, profile_name2)

    def test_provision_post_save_MACAddress_update(self):
        # Saving an existing MACAddress updates the Node with which it's
        # associated.
        node_model = factory.make_node(system_id="frank")
        mac_model = node_model.add_mac_address("12:34:56:78:90:12")
        mac_model.mac_address = "11:22:33:44:55:66"
        mac_model.save()
        node = self.papi.get_nodes_by_name(["frank"])["frank"]
        self.assertEqual(["11:22:33:44:55:66"], node["mac_addresses"])

    def test_provision_post_delete_Node(self):
        node_model = factory.make_node(system_id="frank")
        provisioning.provision_post_save_Node(
            sender=Node, instance=node_model, created=True)
        provisioning.provision_post_delete_Node(
            sender=Node, instance=node_model)
        # The node is deleted, but the profile and distro remain.
        self.assertNotEqual({}, self.papi.get_distros())
        self.assertNotEqual({}, self.papi.get_profiles())
        self.assertEqual({}, self.papi.get_nodes_by_name(["frank"]))

    def test_provision_post_delete_MACAddress(self):
        # Deleting a MACAddress updates the Node with which it's associated.
        node_model = factory.make_node(system_id="frank")
        node_model.add_mac_address("12:34:56:78:90:12")
        node_model.remove_mac_address("12:34:56:78:90:12")
        node = self.papi.get_nodes_by_name(["frank"])["frank"]
        self.assertEqual([], node["mac_addresses"])

    def test_metadata_server_url_refers_to_own_metadata_service(self):
        self.assertEqual(
            "%s/metadata/"
            % Config.objects.get_config('maas_url').rstrip('/'),
            get_metadata_server_url())

    def test_metadata_server_url_includes_script_name(self):
        self.patch(settings, "FORCE_SCRIPT_NAME", "/MAAS")
        self.assertEqual(
            "%s/MAAS/metadata/"
            % Config.objects.get_config('maas_url').rstrip('/'),
            get_metadata_server_url())

    def test_compose_preseed_for_commissioning_node_produces_yaml(self):
        node = factory.make_node(status=NODE_STATUS.COMMISSIONING)
        preseed = yaml.load(compose_preseed(node))
        self.assertIn('datasource', preseed)
        self.assertIn('MAAS', preseed['datasource'])
        self.assertThat(
            preseed['datasource']['MAAS'],
            KeysEqual(
                'metadata_url', 'consumer_key', 'token_key', 'token_secret'))

    def test_compose_preseed_includes_metadata_url(self):
        node = factory.make_node(status=NODE_STATUS.READY)
        self.assertIn(get_metadata_server_url(), compose_preseed(node))

    def test_compose_preseed_for_commissioning_includes_metadata_url(self):
        node = factory.make_node(status=NODE_STATUS.COMMISSIONING)
        preseed = yaml.load(compose_preseed(node))
        self.assertEqual(
            get_metadata_server_url(),
            preseed['datasource']['MAAS']['metadata_url'])

    def test_compose_preseed_includes_node_oauth_token(self):
        node = factory.make_node(status=NODE_STATUS.READY)
        preseed = compose_preseed(node)
        token = NodeKey.objects.get_token_for_node(node)
        self.assertIn('oauth_consumer_key=%s' % token.consumer.key, preseed)
        self.assertIn('oauth_token_key=%s' % token.key, preseed)
        self.assertIn('oauth_token_secret=%s' % token.secret, preseed)

    def test_compose_preseed_for_commissioning_includes_auth_token(self):
        node = factory.make_node(status=NODE_STATUS.COMMISSIONING)
        preseed = yaml.load(compose_preseed(node))
        maas_dict = preseed['datasource']['MAAS']
        token = NodeKey.objects.get_token_for_node(node)
        self.assertEqual(token.consumer.key, maas_dict['consumer_key'])
        self.assertEqual(token.key, maas_dict['token_key'])
        self.assertEqual(token.secret, maas_dict['token_secret'])

    def test_papi_xmlrpc_faults_are_reported_helpfully(self):

        def raise_fault(*args, **kwargs):
            raise Fault(8002, factory.getRandomString())

        self.papi.patch('add_node', raise_fault)

        with ExpectedException(MAASAPIException, ".*provisioning server.*"):
            self.papi.add_node('node', 'profile', 'power', '')

    def test_provisioning_errors_are_reported_helpfully(self):

        def raise_provisioning_error(*args, **kwargs):
            raise Fault(PSERV_FAULT.NO_COBBLER, factory.getRandomString())

        self.papi.patch('add_node', raise_provisioning_error)

        with ExpectedException(MAASAPIException, ".*Cobbler.*"):
            self.papi.add_node('node', 'profile', 'power', '')

    def test_present_user_friendly_fault_describes_pserv_fault(self):
        self.assertIn(
            "provisioning server",
            present_user_friendly_fault(Fault(8002, 'error')).message)

    def test_present_user_friendly_fault_covers_all_pserv_faults(self):
        all_pserv_faults = set(map_enum(PSERV_FAULT).values())
        presentable_pserv_faults = set(PRESENTATIONS.keys())
        self.assertItemsEqual([], all_pserv_faults - presentable_pserv_faults)

    def test_present_user_friendly_fault_rerepresents_all_pserv_faults(self):
        fault_string = factory.getRandomString()
        for fault_code in map_enum(PSERV_FAULT).values():
            original_fault = Fault(fault_code, fault_string)
            new_fault = present_user_friendly_fault(original_fault)
            self.assertNotEqual(fault_string, new_fault.message)

    def test_present_user_friendly_fault_describes_cobbler_fault(self):
        friendly_fault = present_user_friendly_fault(
            Fault(PSERV_FAULT.NO_COBBLER, factory.getRandomString()))
        friendly_text = friendly_fault.message
        self.assertIn("unable to reach", friendly_text)
        self.assertIn("Cobbler", friendly_text)

    def test_present_user_friendly_fault_describes_cobbler_auth_fail(self):
        friendly_fault = present_user_friendly_fault(
            Fault(PSERV_FAULT.COBBLER_AUTH_FAILED, factory.getRandomString()))
        friendly_text = friendly_fault.message
        self.assertIn("failed to authenticate", friendly_text)
        self.assertIn("Cobbler", friendly_text)

    def test_present_user_friendly_fault_describes_cobbler_auth_error(self):
        friendly_fault = present_user_friendly_fault(
            Fault(PSERV_FAULT.COBBLER_AUTH_ERROR, factory.getRandomString()))
        friendly_text = friendly_fault.message
        self.assertIn("authentication token", friendly_text)
        self.assertIn("Cobbler", friendly_text)

    def test_present_user_friendly_fault_describes_missing_profile(self):
        profile = factory.getRandomString()
        friendly_fault = present_user_friendly_fault(
            Fault(
                PSERV_FAULT.NO_SUCH_PROFILE,
                "invalid profile name: %s" % profile))
        friendly_text = friendly_fault.message
        self.assertIn(profile, friendly_text)
        self.assertIn("maas-import-isos", friendly_text)

    def test_present_user_friendly_fault_describes_generic_cobbler_fail(self):
        error_text = factory.getRandomString()
        friendly_fault = present_user_friendly_fault(
            Fault(PSERV_FAULT.GENERIC_COBBLER_ERROR, error_text))
        friendly_text = friendly_fault.message
        self.assertIn("Cobbler", friendly_text)
        self.assertIn(error_text, friendly_text)

    def test_present_user_friendly_fault_returns_None_for_other_fault(self):
        self.assertIsNone(present_user_friendly_fault(Fault(9999, "!!!")))


class TestProvisioningWithFake(ProvisioningTests, ProvisioningFakeFactory,
                               TestCase):
    """Tests for the Provisioning API using a fake."""

    run_tests_with = AsynchronousDeferredRunTest.make_factory(timeout=5)

    def setUp(self):
        super(TestProvisioningWithFake, self).setUp()
        self.papi = provisioning.get_provisioning_api_proxy()

    def test_provision_post_save_Node_set_netboot_enabled(self):
        # When a node is under MAAS's control - i.e. not allocated and not
        # retired - it is always configured for netbooting. When the node is
        # allocated, netbooting is left alone; its state may change in
        # response to interactions between the node and the provisioning
        # server and MAAS ought to leave that alone. When the node is retired
        # netbooting is disabled.
        expected = {
            NODE_STATUS.DECLARED: True,
            NODE_STATUS.COMMISSIONING: True,
            NODE_STATUS.FAILED_TESTS: True,
            NODE_STATUS.MISSING: True,
            NODE_STATUS.READY: True,
            NODE_STATUS.RESERVED: True,
            NODE_STATUS.ALLOCATED: None,  # No setting.
            NODE_STATUS.RETIRED: False,
            }
        nodes = {
            status: factory.make_node(status=status)
            for status, title in NODE_STATUS_CHOICES
            }
        pserv_nodes = {
            status: node.system_id
            for status, node in nodes.items()
            }
        observed = {
            status: self.papi.nodes[pserv_node].get("netboot_enabled")
            for status, pserv_node in pserv_nodes.items()
            }
        self.assertEqual(expected, observed)
