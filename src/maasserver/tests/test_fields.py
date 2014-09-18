# Copyright 2012-2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test custom model fields."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

import json
from random import randint

from django.core import serializers
from django.core.exceptions import ValidationError
from django.db import (
    connection,
    DatabaseError,
    )
from django.db.models import BinaryField
from maasserver.enum import NODEGROUPINTERFACE_MANAGEMENT
from maasserver.fields import (
    EditableBinaryField,
    LargeObjectField,
    LargeObjectFile,
    MAC,
    NodeGroupFormField,
    register_mac_type,
    validate_mac,
    VerboseRegexField,
    VerboseRegexValidator,
    )
from maasserver.models import (
    MACAddress,
    NodeGroup,
    )
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.tests.models import (
    JSONFieldModel,
    LargeObjectFieldModel,
    MAASIPAddressFieldModel,
    XMLFieldModel,
    )
from maastesting.djangotestcase import TestModelMixin
from maastesting.matchers import MockCalledOnceWith
from psycopg2 import OperationalError
from psycopg2.extensions import ISQLQuote


class TestNodeGroupFormField(MAASServerTestCase):

    def test_label_from_instance_tolerates_missing_interface(self):
        nodegroup = factory.make_NodeGroup()
        nodegroup.nodegroupinterface_set.all().delete()
        self.assertEqual(
            nodegroup.name,
            NodeGroupFormField().label_from_instance(nodegroup))

    def test_label_from_instance_shows_name_and_address(self):
        nodegroup = factory.make_NodeGroup()
        interface = factory.make_NodeGroupInterface(
            nodegroup, management=NODEGROUPINTERFACE_MANAGEMENT.DHCP)
        self.assertEqual(
            '%s: %s' % (nodegroup.name, interface.ip),
            NodeGroupFormField().label_from_instance(nodegroup))

    def test_clean_defaults_to_master(self):
        spellings_for_none = [None, '', b'']
        field = NodeGroupFormField()
        self.assertEqual(
            [NodeGroup.objects.ensure_master()] * len(spellings_for_none),
            [field.clean(spelling) for spelling in spellings_for_none])

    def test_clean_accepts_nodegroup(self):
        nodegroup = factory.make_NodeGroup()
        self.assertEqual(nodegroup, NodeGroupFormField().clean(nodegroup))

    def test_clean_accepts_id_as_unicode(self):
        nodegroup = factory.make_NodeGroup()
        self.assertEqual(
            nodegroup,
            NodeGroupFormField().clean("%s" % nodegroup.id))

    def test_clean_accepts_id_as_bytes(self):
        nodegroup = factory.make_NodeGroup()
        self.assertEqual(
            nodegroup,
            NodeGroupFormField().clean(("%s" % nodegroup.id).encode('ascii')))

    def test_clean_accepts_uuid(self):
        nodegroup = factory.make_NodeGroup()
        self.assertEqual(
            nodegroup,
            NodeGroupFormField().clean(nodegroup.uuid))

    def test_clean_accepts_uuid_as_bytes(self):
        nodegroup = factory.make_NodeGroup()
        self.assertEqual(
            nodegroup,
            NodeGroupFormField().clean(nodegroup.uuid.encode('ascii')))

    def test_clean_accepts_cluster_name(self):
        nodegroup = factory.make_NodeGroup()
        self.assertEqual(
            nodegroup,
            NodeGroupFormField().clean(nodegroup.cluster_name))

    def test_clean_accepts_cluster_name_as_bytes(self):
        nodegroup = factory.make_NodeGroup()
        self.assertEqual(
            nodegroup,
            NodeGroupFormField().clean(nodegroup.cluster_name.encode('ascii')))

    def test_clean_accepts_numeric_cluster_name(self):
        # This cluster has a name that looks just like a number.  Pick a number
        # that's highly unlikely to clash with the node's ID.
        cluster_name = '%s' % randint(1000000, 10000000)
        nodegroup = factory.make_NodeGroup(cluster_name=cluster_name)
        self.assertEqual(nodegroup, NodeGroupFormField().clean(cluster_name))

    def test_clean_rejects_unknown_nodegroup(self):
        self.assertRaises(
            ValidationError,
            NodeGroupFormField().clean, factory.make_name('nonesuch'))


class TestMAC(MAASServerTestCase):

    def test_conform_accepts_ISQLQuote(self):
        mac = MAC(None)
        self.assertEqual(mac, mac.__conform__(ISQLQuote))

    def test_get_raw_returns_wrapped_None(self):
        self.assertIsNone(MAC(None).get_raw())

    def test_get_raw_returns_wrapped_address(self):
        addr = factory.make_mac_address()
        self.assertEqual(addr, MAC(addr).get_raw())

    def test_get_raw_punches_through_double_wrapping(self):
        addr = factory.make_mac_address()
        self.assertEqual(addr, MAC(MAC(addr)).get_raw())

    def test_getquoted_returns_NULL_for_None(self):
        self.assertEqual("NULL", MAC(None).getquoted())

    def test_getquoted_returns_SQL_for_MAC(self):
        addr = factory.make_mac_address()
        self.assertEqual("'%s'::macaddr" % addr, MAC(addr).getquoted())

    def test_getquoted_punches_through_double_wrapping(self):
        addr = factory.make_mac_address()
        self.assertEqual("'%s'::macaddr" % addr, MAC(MAC(addr)).getquoted())

    def test_mac_equals_self(self):
        mac = factory.make_MAC()
        self.assertTrue(mac == mac)

    def test_mac_equals_identical_mac(self):
        addr = factory.make_mac_address()
        self.assertTrue(MAC(addr) == MAC(addr))

    def test_eq_punches_through_double_wrapping_on_self(self):
        mac = factory.make_MAC()
        self.assertTrue(MAC(mac) == mac)

    def test_eq_punches_through_double_wrapping_on_other(self):
        mac = factory.make_MAC()
        self.assertTrue(mac == MAC(mac))

    def test_eq_punches_through_double_double_wrappings(self):
        mac = factory.make_MAC()
        self.assertTrue(MAC(mac) == MAC(mac))

    def test_mac_does_not_equal_other(self):
        self.assertFalse(factory.make_MAC() == factory.make_MAC())

    def test_mac_differs_from_other(self):
        self.assertTrue(factory.make_MAC() != factory.make_MAC())

    def test_mac_does_not_differ_from_self(self):
        mac = factory.make_MAC()
        self.assertFalse(mac != mac)

    def test_none_mac_equals_none(self):
        # This is a special case that Django seems to need: it does
        # "value in validators.EMPTY_VALUES".
        self.assertEqual(None, MAC(None))

    def test_mac_address_does_not_equal_none(self):
        self.assertIsNotNone(factory.make_MAC())

    def test_ne_punches_through_double_wrapping_on_self(self):
        mac = factory.make_MAC()
        self.assertFalse(MAC(mac) != mac)

    def test_ne_punches_through_double_wrapping_on_other(self):
        mac = factory.make_MAC()
        self.assertFalse(mac != MAC(mac))

    def test_ne_punches_through_double_double_wrapping(self):
        mac = factory.make_MAC()
        self.assertFalse(MAC(mac) != MAC(mac))

    def test_different_macs_hash_differently(self):
        mac1 = factory.make_MAC()
        mac2 = factory.make_MAC()
        self.assertItemsEqual(set([mac1, mac2]), [mac1, mac2])

    def test_identical_macs_hash_identically(self):
        addr = factory.make_mac_address()
        self.assertItemsEqual(
            set([MAC(addr), MAC(addr), MAC(MAC(addr)), addr]),
            [addr])

    def test_django_serializes_MAC_to_JSON(self):
        mac = factory.make_MACAddress()
        query = MACAddress.objects.filter(id=mac.id)
        output = serializers.serialize('json', query)
        self.assertIn(json.dumps(mac.mac_address.get_raw()), output)
        self.assertIn('"%s"' % mac.mac_address.get_raw(), output)

    def test_register_mac_type_is_idempotent(self):
        register_mac_type(connection.cursor())
        register_mac_type(connection.cursor())
        # The test is that we get here without crashing.
        pass


class TestVerboseRegexValidator(MAASServerTestCase):

    def test_VerboseRegexValidator_validates_value(self):
        validator = VerboseRegexValidator(
            regex="test", message="Unknown value")
        self.assertIsNone(validator('test'))

    def test_VerboseRegexValidator_validation_error_includes_value(self):
        message = "Unknown value: %(value)s"
        validator = VerboseRegexValidator(regex="test", message=message)
        value = factory.make_name('value')
        error = self.assertRaises(ValidationError, validator, value)
        self.assertEqual(message % {'value': value}, error.message)


class TestVerboseRegexField(MAASServerTestCase):

    def test_VerboseRegexField_accepts_valid_value(self):
        field = VerboseRegexField(regex="test", message="Unknown value")
        self.assertEqual('test', field.clean('test'))

    def test_VerboseRegexField_validation_error_includes_value(self):
        message = "Unknown value: %(value)s"
        field = VerboseRegexField(regex="test", message=message)
        value = factory.make_name('value')
        error = self.assertRaises(ValidationError, field.clean, value)
        self.assertEqual([message % {'value': value}], error.messages)


class TestMACAddressField(MAASServerTestCase):

    def test_mac_address_is_stored_normalized_and_loaded(self):
        stored_mac = factory.make_MACAddress(' AA-bb-CC-dd-EE-Ff ')
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


class TestJSONObjectField(TestModelMixin, MAASServerTestCase):

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
            name = factory.make_string()
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


class TestXMLField(TestModelMixin, MAASServerTestCase):

    app = 'maasserver.tests'

    def test_loads_string(self):
        name = factory.make_string()
        value = "<test/>"
        XMLFieldModel.objects.create(name=name, value=value)
        instance = XMLFieldModel.objects.get(name=name)
        self.assertEqual(value, instance.value)

    def test_lookup_xpath_exists_result(self):
        name = factory.make_string()
        XMLFieldModel.objects.create(name=name, value="<test/>")
        result = XMLFieldModel.objects.raw(
            "SELECT * FROM docs WHERE xpath_exists(%s, value)", ["//test"])
        self.assertEqual(name, result[0].name)

    def test_lookup_xpath_exists_no_result(self):
        name = factory.make_string()
        XMLFieldModel.objects.create(name=name, value="<test/>")
        result = XMLFieldModel.objects.raw(
            "SELECT * FROM docs WHERE xpath_exists(%s, value)", ["//miss"])
        self.assertEqual([], list(result))

    def test_save_empty_rejected(self):
        self.assertRaises(
            DatabaseError, XMLFieldModel.objects.create, value="")

    def test_save_non_wellformed_rejected(self):
        self.assertRaises(
            DatabaseError, XMLFieldModel.objects.create, value="<bad>")

    def test_lookup_none(self):
        XMLFieldModel.objects.create(value=None)
        test_instance = XMLFieldModel.objects.get(value__isnull=True)
        self.assertIsNone(test_instance.value)

    def test_lookup_exact_unsupported(self):
        self.assertRaises(TypeError, XMLFieldModel.objects.get, value="")


class TestEditableBinaryField(MAASServerTestCase):

    def test_is_BinaryField(self):
        self.assertIsInstance(EditableBinaryField(), BinaryField)

    def test_is_editable(self):
        self.assertTrue(EditableBinaryField().editable)


class TestMAASIPAddressField(TestModelMixin, MAASServerTestCase):

    app = 'maasserver.tests'

    def test_uses_ip_comparison(self):
        ip_object = MAASIPAddressFieldModel.objects.create(
            ip_address='192.0.2.99')
        results = MAASIPAddressFieldModel.objects.filter(
            ip_address__lte='192.0.2.100')
        self.assertItemsEqual([ip_object], results)


class TestLargeObjectField(TestModelMixin, MAASServerTestCase):

    app = 'maasserver.tests'

    def test_stores_data(self):
        data = factory.make_string()
        test_name = factory.make_name('name')
        test_instance = LargeObjectFieldModel(name=test_name)
        large_object = LargeObjectFile()
        with large_object.open('wb') as stream:
            stream.write(data)
        test_instance.large_object = large_object
        test_instance.save()
        test_instance = LargeObjectFieldModel.objects.get(name=test_name)
        with test_instance.large_object.open('rb') as stream:
            saved_data = stream.read()
        self.assertEqual(data, saved_data)

    def test_with_exit_calls_close(self):
        data = factory.make_string()
        large_object = LargeObjectFile()
        with large_object.open('wb') as stream:
            self.addCleanup(large_object.close)
            mock_close = self.patch(large_object, 'close')
            stream.write(data)
        self.assertThat(mock_close, MockCalledOnceWith())

    def test_unlink(self):
        data = factory.make_string()
        large_object = LargeObjectFile()
        with large_object.open('wb') as stream:
            stream.write(data)
        oid = large_object.oid
        large_object.unlink()
        self.assertEqual(0, large_object.oid)
        self.assertRaises(
            OperationalError,
            connection.connection.lobject, oid)

    def test_interates_on_block_size(self):
        # String size is multiple of block_size in the testing model
        data = factory.make_string(10 * 2)
        test_name = factory.make_name('name')
        test_instance = LargeObjectFieldModel(name=test_name)
        large_object = LargeObjectFile()
        with large_object.open('wb') as stream:
            stream.write(data)
        test_instance.large_object = large_object
        test_instance.save()
        test_instance = LargeObjectFieldModel.objects.get(name=test_name)
        with test_instance.large_object.open('rb') as stream:
            offset = 0
            for block in stream:
                self.assertEqual(data[offset:offset + 10], block)
                offset += 10

    def test_get_db_prep_value_returns_None_when_value_None(self):
        field = LargeObjectField()
        self.assertEqual(None, field.get_db_prep_value(None))

    def test_get_db_prep_value_returns_oid_when_value_LargeObjectFile(self):
        oid = randint(1, 100)
        field = LargeObjectField()
        obj_file = LargeObjectFile()
        obj_file.oid = oid
        self.assertEqual(oid, field.get_db_prep_value(obj_file))

    def test_get_db_prep_value_raises_error_when_oid_less_than_zero(self):
        oid = randint(-100, 0)
        field = LargeObjectField()
        obj_file = LargeObjectFile()
        obj_file.oid = oid
        self.assertRaises(AssertionError, field.get_db_prep_value, obj_file)

    def test_get_db_prep_value_raises_error_when_not_LargeObjectFile(self):
        field = LargeObjectField()
        self.assertRaises(
            AssertionError, field.get_db_prep_value, factory.make_string())

    def test_to_python_returns_None_when_value_None(self):
        field = LargeObjectField()
        self.assertEqual(None, field.to_python(None))

    def test_to_python_returns_value_when_value_LargeObjectFile(self):
        field = LargeObjectField()
        obj_file = LargeObjectFile()
        self.assertEqual(obj_file, field.to_python(obj_file))

    def test_to_python_returns_LargeObjectFile_when_value_int(self):
        oid = randint(1, 100)
        field = LargeObjectField()
        obj_file = field.to_python(oid)
        self.assertEqual(oid, obj_file.oid)

    def test_to_python_returns_LargeObjectFile_when_value_long(self):
        oid = long(randint(1, 100))
        field = LargeObjectField()
        obj_file = field.to_python(oid)
        self.assertEqual(oid, obj_file.oid)

    def test_to_python_raises_error_when_not_valid_type(self):
        field = LargeObjectField()
        self.assertRaises(
            AssertionError, field.to_python, factory.make_string())
