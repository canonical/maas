# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `maasserver.provisioning`."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = []

from xmlrpclib import Fault

from maasserver.enum import NODE_STATUS
from maasserver.provisioning import (
    compose_preseed,
    DETAILED_PRESENTATIONS,
    present_detailed_user_friendly_fault,
    present_user_friendly_fault,
    ProvisioningTransport,
    SHORT_PRESENTATIONS,
    )
from maasserver.testing.factory import factory
from maasserver.testing.testcase import TestCase
from maasserver.utils import (
    absolute_reverse,
    map_enum,
    )
from metadataserver.models import NodeKey
from provisioningserver.enum import PSERV_FAULT
from testtools.matchers import (
    KeysEqual,
    StartsWith,
    )
import yaml


class TestHelpers(TestCase):
    """Tests for helpers that don't actually need any kind of pserv."""

    def test_compose_preseed_for_commissioning_node_produces_yaml(self):
        node = factory.make_node(status=NODE_STATUS.COMMISSIONING)
        preseed = yaml.safe_load(compose_preseed(node))
        self.assertIn('datasource', preseed)
        self.assertIn('MAAS', preseed['datasource'])
        self.assertThat(
            preseed['datasource']['MAAS'],
            KeysEqual(
                'metadata_url', 'consumer_key', 'token_key', 'token_secret'))

    def test_compose_preseed_for_commissioning_node_has_header(self):
        node = factory.make_node(status=NODE_STATUS.COMMISSIONING)
        self.assertThat(compose_preseed(node), StartsWith("#cloud-config\n"))

    def test_compose_preseed_includes_metadata_url(self):
        node = factory.make_node(status=NODE_STATUS.READY)
        self.assertIn(absolute_reverse('metadata'), compose_preseed(node))

    def test_compose_preseed_for_commissioning_includes_metadata_url(self):
        node = factory.make_node(status=NODE_STATUS.COMMISSIONING)
        preseed = yaml.safe_load(compose_preseed(node))
        self.assertEqual(
            absolute_reverse('metadata'),
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
        preseed = yaml.safe_load(compose_preseed(node))
        maas_dict = preseed['datasource']['MAAS']
        token = NodeKey.objects.get_token_for_node(node)
        self.assertEqual(token.consumer.key, maas_dict['consumer_key'])
        self.assertEqual(token.key, maas_dict['token_key'])
        self.assertEqual(token.secret, maas_dict['token_secret'])

    def test_present_detailed_user_friendly_fault_describes_pserv_fault(self):
        self.assertIn(
            "provisioning server",
            present_user_friendly_fault(Fault(8002, 'error')).message)

    def test_present_detailed_fault_covers_all_pserv_faults(self):
        all_pserv_faults = set(map_enum(PSERV_FAULT).values())
        presentable_pserv_faults = set(DETAILED_PRESENTATIONS.keys())
        self.assertItemsEqual([], all_pserv_faults - presentable_pserv_faults)

    def test_present_detailed_fault_rerepresents_all_pserv_faults(self):
        fault_string = factory.getRandomString()
        for fault_code in map_enum(PSERV_FAULT).values():
            original_fault = Fault(fault_code, fault_string)
            new_fault = present_detailed_user_friendly_fault(original_fault)
            self.assertNotEqual(fault_string, new_fault.message)

    def test_present_detailed_fault_describes_cobbler_fault(self):
        friendly_fault = present_detailed_user_friendly_fault(
            Fault(PSERV_FAULT.NO_COBBLER, factory.getRandomString()))
        friendly_text = friendly_fault.message
        self.assertIn("unable to reach", friendly_text)
        self.assertIn("Cobbler", friendly_text)

    def test_present_detailed_fault_describes_cobbler_auth_fail(self):
        friendly_fault = present_detailed_user_friendly_fault(
            Fault(PSERV_FAULT.COBBLER_AUTH_FAILED, factory.getRandomString()))
        friendly_text = friendly_fault.message
        self.assertIn("failed to authenticate", friendly_text)
        self.assertIn("Cobbler", friendly_text)

    def test_present_detailed_fault_describes_cobbler_auth_error(self):
        friendly_fault = present_detailed_user_friendly_fault(
            Fault(PSERV_FAULT.COBBLER_AUTH_ERROR, factory.getRandomString()))
        friendly_text = friendly_fault.message
        self.assertIn("authentication token", friendly_text)
        self.assertIn("Cobbler", friendly_text)

    def test_present_detailed_fault_describes_missing_profile(self):
        profile = factory.getRandomString()
        friendly_fault = present_detailed_user_friendly_fault(
            Fault(
                PSERV_FAULT.NO_SUCH_PROFILE,
                "invalid profile name: %s" % profile))
        friendly_text = friendly_fault.message
        self.assertIn(profile, friendly_text)
        self.assertIn("profile", friendly_text)

    def test_present_detailed_fault_describes_generic_cobbler_fail(self):
        error_text = factory.getRandomString()
        friendly_fault = present_detailed_user_friendly_fault(
            Fault(PSERV_FAULT.GENERIC_COBBLER_ERROR, error_text))
        friendly_text = friendly_fault.message
        self.assertIn("Cobbler", friendly_text)
        self.assertIn(error_text, friendly_text)

    def test_present_detailed_fault_returns_None_for_other_fault(self):
        self.assertIsNone(
            present_detailed_user_friendly_fault(Fault(9999, "!!!")))

    def test_present_user_friendly_fault_describes_pserv_fault(self):
        self.assertIn(
            "provisioning server",
            present_user_friendly_fault(Fault(8002, 'error')).message)

    def test_present_user_friendly_fault_covers_all_pserv_faults(self):
        all_pserv_faults = set(map_enum(PSERV_FAULT).values())
        presentable_pserv_faults = set(SHORT_PRESENTATIONS.keys())
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
        self.assertIn("Unable to reach the Cobbler server", friendly_text)

    def test_present_user_friendly_fault_describes_cobbler_auth_fail(self):
        friendly_fault = present_user_friendly_fault(
            Fault(PSERV_FAULT.COBBLER_AUTH_FAILED, factory.getRandomString()))
        friendly_text = friendly_fault.message
        self.assertIn(
            "Failed to authenticate with the Cobbler server", friendly_text)

    def test_present_user_friendly_fault_describes_cobbler_auth_error(self):
        friendly_fault = present_user_friendly_fault(
            Fault(PSERV_FAULT.COBBLER_AUTH_ERROR, factory.getRandomString()))
        friendly_text = friendly_fault.message
        self.assertIn(
            "Failed to authenticate with the Cobbler server", friendly_text)

    def test_present_user_friendly_fault_describes_missing_profile(self):
        profile = factory.getRandomString()
        friendly_fault = present_user_friendly_fault(
            Fault(
                PSERV_FAULT.NO_SUCH_PROFILE,
                "invalid profile name: %s" % profile))
        friendly_text = friendly_fault.message
        self.assertIn(profile, friendly_text)

    def test_present_user_friendly_fault_describes_generic_cobbler_fail(self):
        error_text = factory.getRandomString()
        friendly_fault = present_user_friendly_fault(
            Fault(PSERV_FAULT.GENERIC_COBBLER_ERROR, error_text))
        friendly_text = friendly_fault.message
        self.assertIn(
            "Unknown problem encountered with the Cobbler server.",
            friendly_text)


class TestProvisioningTransport(TestCase):
    """Tests for :class:`ProvisioningTransport`."""

    def test_make_connection(self):
        transport = ProvisioningTransport()
        connection = transport.make_connection("nowhere.example.com")
        # The connection has not yet been established.
        self.assertIsNone(connection.sock)
        # The desired timeout has been modified.
        self.assertEqual(transport.timeout, connection.timeout)
