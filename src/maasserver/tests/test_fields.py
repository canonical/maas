# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test custom model fields."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = []

from django.core.exceptions import ValidationError
from django.db import DatabaseError
from maasserver.fields import (
    NodeGroupFormField,
    validate_mac,
    )
from maasserver.models import (
    MACAddress,
    NodeGroup,
    NodeGroupInterface,
    )
from maasserver.testing.factory import factory
from maasserver.testing.testcase import (
    TestCase,
    TestModelTestCase,
    )
from maasserver.tests.models import (
    JSONFieldModel,
    XMLFieldModel,
    )


class TestNodeGroupFormField(TestCase):

    def test_label_from_instance_tolerates_missing_interface(self):
        nodegroup = factory.make_node_group()
        interface = nodegroup.get_managed_interface()
        if interface is not None:
            NodeGroupInterface.objects.filter(id=interface.id).delete()
        self.assertEqual(
            nodegroup.name,
            NodeGroupFormField().label_from_instance(nodegroup))

    def test_label_from_instance_shows_name_and_address(self):
        nodegroup = factory.make_node_group()
        self.assertEqual(
            '%s: %s' % (nodegroup.name, nodegroup.get_managed_interface().ip),
            NodeGroupFormField().label_from_instance(nodegroup))

    def test_clean_defaults_to_master(self):
        spellings_for_none = [None, '', b'']
        field = NodeGroupFormField()
        self.assertEqual(
            [NodeGroup.objects.ensure_master()] * len(spellings_for_none),
            [field.clean(spelling) for spelling in spellings_for_none])

    def test_clean_accepts_nodegroup(self):
        nodegroup = factory.make_node_group()
        self.assertEqual(nodegroup, NodeGroupFormField().clean(nodegroup))

    def test_clean_accepts_id_as_text(self):
        nodegroup = factory.make_node_group()
        self.assertEqual(
            nodegroup,
            NodeGroupFormField().clean("%s" % nodegroup.id))

    def test_clean_finds_nodegroup_by_network_address(self):
        nodegroup = factory.make_node_group(
            ip='192.168.28.1', subnet_mask='255.255.255.0')
        self.assertEqual(
            nodegroup,
            NodeGroupFormField().clean('192.168.28.0'))

    def test_find_nodegroup_looks_up_nodegroup_by_controller_ip(self):
        nodegroup = factory.make_node_group()
        self.assertEqual(
            nodegroup,
            NodeGroupFormField().clean(nodegroup.get_managed_interface().ip))

    def test_find_nodegroup_accepts_any_ip_in_nodegroup_subnet(self):
        nodegroup = factory.make_node_group(
            ip='192.168.41.1', subnet_mask='255.255.255.0')
        self.assertEqual(
            nodegroup,
            NodeGroupFormField().clean('192.168.41.199'))

    def test_find_nodegroup_reports_if_not_found(self):
        self.assertRaises(
            ValidationError,
            NodeGroupFormField().clean,
            factory.getRandomIPAddress())

    def test_find_nodegroup_reports_if_multiple_matches(self):
        factory.make_node_group(ip='10.0.0.1', subnet_mask='255.0.0.0')
        factory.make_node_group(ip='10.1.1.1', subnet_mask='255.255.255.0')
        self.assertRaises(
            NodeGroup.MultipleObjectsReturned,
            NodeGroupFormField().clean, '10.1.1.2')

    def test_find_nodegroup_handles_multiple_matches_on_same_nodegroup(self):
        nodegroup = factory.make_node_group(
            ip='10.0.0.1', subnet_mask='255.0.0.0')
        NodeGroupInterface.objects.create(
            nodegroup=nodegroup, ip='10.0.0.2', subnet_mask='255.0.0.0',
            interface='eth71')
        NodeGroupInterface.objects.create(
            nodegroup=nodegroup, ip='10.0.0.3', subnet_mask='255.0.0.0',
            interface='eth72')
        self.assertEqual(nodegroup, NodeGroupFormField().clean('10.0.0.9'))


class TestMACAddressField(TestCase):

    def test_mac_address_is_stored_normalized_and_loaded(self):
        stored_mac = factory.make_mac_address(' AA-bb-CC-dd-EE-Ff ')
        stored_mac.save()
        loaded_mac = MACAddress.objects.get(id=stored_mac.id)
        self.assertEqual('aa:bb:cc:dd:ee:ff', loaded_mac.mac_address)

    def test_accepts_colon_separated_octets(self):
        validate_mac('00:aa:22:cc:44:dd')
        # No error.
        pass

    def test_accepts_dash_separated_octets(self):
        validate_mac('00-aa-22-cc-44-dd')
        # No error.
        pass

    def test_accepts_upper_and_lower_case(self):
        validate_mac('AA:BB:CC:dd:ee:ff')
        # No error.
        pass

    def test_accepts_leading_and_trailing_whitespace(self):
        validate_mac(' AA:BB:CC:DD:EE:FF ')
        # No error.
        pass

    def test_rejects_short_mac(self):
        self.assertRaises(ValidationError, validate_mac, '00:11:22:33:44')

    def test_rejects_long_mac(self):
        self.assertRaises(
            ValidationError, validate_mac, '00:11:22:33:44:55:66')

    def test_rejects_short_octet(self):
        self.assertRaises(ValidationError, validate_mac, '00:1:22:33:44:55')

    def test_rejects_long_octet(self):
        self.assertRaises(ValidationError, validate_mac, '00:11:222:33:44:55')


class TestJSONObjectField(TestModelTestCase):

    app = 'maasserver.tests'

    def test_stores_types(self):
        values = [
            None,
            True,
            False,
            3.33,
            "A simple string",
            [1, 2.43, "3"],
            {"not": 5, "another": "test"},
            ]
        for value in values:
            name = factory.getRandomString()
            test_instance = JSONFieldModel(name=name, value=value)
            test_instance.save()

            test_instance = JSONFieldModel.objects.get(name=name)
            self.assertEqual(value, test_instance.value)

    def test_field_exact_lookup(self):
        # Value can be query via an 'exact' lookup.
        obj = [4, 6, {}]
        JSONFieldModel.objects.create(value=obj)
        test_instance = JSONFieldModel.objects.get(value=obj)
        self.assertEqual(obj, test_instance.value)

    def test_field_none_lookup(self):
        # Value can be queried via a 'isnull' lookup.
        JSONFieldModel.objects.create(value=None)
        test_instance = JSONFieldModel.objects.get(value__isnull=True)
        self.assertIsNone(test_instance.value)

    def test_field_another_lookup_fails(self):
        # Others lookups are not allowed.
        self.assertRaises(TypeError, JSONFieldModel.objects.get, value__gte=3)


class TestXMLField(TestModelTestCase):

    app = 'maasserver.tests'

    def test_loads_string(self):
        name = factory.getRandomString()
        value = "<test/>"
        XMLFieldModel.objects.create(name=name, value=value)
        instance = XMLFieldModel.objects.get(name=name)
        self.assertEqual(value, instance.value)

    def test_lookup_xpath_exists_result(self):
        name = factory.getRandomString()
        XMLFieldModel.objects.create(name=name, value="<test/>")
        result = XMLFieldModel.objects.raw(
            "SELECT * FROM docs WHERE xpath_exists(%s, value)", ["//test"])
        self.assertEqual(name, result[0].name)

    def test_lookup_xpath_exists_no_result(self):
        name = factory.getRandomString()
        XMLFieldModel.objects.create(name=name, value="<test/>")
        result = XMLFieldModel.objects.raw(
            "SELECT * FROM docs WHERE xpath_exists(%s, value)", ["//miss"])
        self.assertEqual([], list(result))

    def test_save_empty_rejected(self):
        self.assertRaises(DatabaseError, XMLFieldModel.objects.create,
            value="")

    def test_save_non_wellformed_rejected(self):
        self.assertRaises(DatabaseError, XMLFieldModel.objects.create,
            value="<bad>")

    def test_lookup_none(self):
        XMLFieldModel.objects.create(value=None)
        test_instance = XMLFieldModel.objects.get(value__isnull=True)
        self.assertIsNone(test_instance.value)

    def test_lookup_exact_unsupported(self):
        self.assertRaises(TypeError, XMLFieldModel.objects.get, value="")
