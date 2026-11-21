# Copyright 2012-2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from random import randint

from django.core.exceptions import ValidationError
from django.db import connection, DatabaseError
from psycopg2 import OperationalError

from maasserver.fields import LargeObjectField, LargeObjectFile
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASLegacyServerTestCase
from maasserver.tests.models import (
    CIDRTestModel,
    IPv4CIDRTestModel,
    LargeObjectFieldModel,
    XMLFieldModel,
)
from maasserver.utils.orm import reload_object


class TestXMLField(MAASLegacyServerTestCase):
    apps = ["maasserver.tests"]

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
            "SELECT * FROM docs WHERE xpath_exists(%s, value)", ["//test"]
        )
        self.assertEqual(name, result[0].name)

    def test_lookup_xpath_exists_no_result(self):
        name = factory.make_string()
        XMLFieldModel.objects.create(name=name, value="<test/>")
        result = XMLFieldModel.objects.raw(
            "SELECT * FROM docs WHERE xpath_exists(%s, value)", ["//miss"]
        )
        self.assertEqual([], list(result))

    def test_save_non_wellformed_rejected(self):
        self.assertRaises(
            DatabaseError, XMLFieldModel.objects.create, value="<bad>"
        )

    def test_lookup_none(self):
        XMLFieldModel.objects.create(value=None)
        test_instance = XMLFieldModel.objects.get(value__isnull=True)
        self.assertIsNone(test_instance.value)


class TestLargeObjectField(MAASLegacyServerTestCase):
    apps = ["maasserver.tests"]

    def test_stores_data(self):
        data = factory.make_bytes()
        test_name = factory.make_name("name")
        test_instance = LargeObjectFieldModel(name=test_name)
        large_object = LargeObjectFile()
        with large_object.open("wb") as stream:
            stream.write(data)
        test_instance.large_object = large_object
        test_instance.save()
        test_instance = LargeObjectFieldModel.objects.get(name=test_name)
        with test_instance.large_object.open("rb") as stream:
            saved_data = stream.read()
        self.assertEqual(data, saved_data)

    def test_insists_on_binary_mode(self):
        message = "Large objects must be opened in binary mode."
        with self.assertRaisesRegex(ValueError, message):
            large_object = LargeObjectFile()
            large_object.open("w")

    def test_with_exit_calls_close(self):
        data = factory.make_bytes()
        large_object = LargeObjectFile()
        with large_object.open("wb") as stream:
            self.addCleanup(large_object.close)
            mock_close = self.patch(large_object, "close")
            stream.write(data)
        mock_close.assert_called_once_with()

    def test_unlink(self):
        data = factory.make_bytes()
        large_object = LargeObjectFile()
        with large_object.open("wb") as stream:
            stream.write(data)
        oid = large_object.oid
        large_object.unlink()
        self.assertEqual(0, large_object.oid)
        self.assertRaises(OperationalError, connection.connection.lobject, oid)

    def test_interates_on_block_size(self):
        # String size is multiple of block_size in the testing model
        data = factory.make_bytes(10 * 2)
        test_name = factory.make_name("name")
        test_instance = LargeObjectFieldModel(name=test_name)
        large_object = LargeObjectFile()
        with large_object.open("wb") as stream:
            stream.write(data)
        test_instance.large_object = large_object
        test_instance.save()
        test_instance = LargeObjectFieldModel.objects.get(name=test_name)
        with test_instance.large_object.open("rb") as stream:
            offset = 0
            for block in stream:
                self.assertEqual(data[offset : offset + 10], block)
                offset += 10

    def test_get_db_prep_value_returns_None_when_value_None(self):
        field = LargeObjectField()
        self.assertIsNone(field.get_db_prep_value(None))

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
            AssertionError, field.get_db_prep_value, factory.make_string()
        )

    def test_to_python_returns_None_when_value_None(self):
        field = LargeObjectField()
        self.assertIsNone(field.to_python(None))

    def test_to_python_returns_value_when_value_LargeObjectFile(self):
        field = LargeObjectField()
        obj_file = LargeObjectFile()
        self.assertEqual(obj_file, field.to_python(obj_file))

    def test_to_python_returns_LargeObjectFile_when_value_int(self):
        oid = randint(1, 100)
        field = LargeObjectField()
        # South normally substitutes a FakeModel here, but with a baseline
        # schema, we can skip the migration that creates LargeObjectField.
        self.patch(field, "model")
        obj_file = field.to_python(oid)
        self.assertEqual(oid, obj_file.oid)

    def test_to_python_returns_LargeObjectFile_when_value_long(self):
        oid = int(randint(1, 100))
        field = LargeObjectField()
        # South normally substitutes a FakeModel here, but with a baseline
        # schema, we can skip the migration that creates LargeObjectField.
        self.patch(field, "model")
        obj_file = field.to_python(oid)
        self.assertEqual(oid, obj_file.oid)

    def test_to_python_raises_error_when_not_valid_type(self):
        field = LargeObjectField()
        self.assertRaises(
            AssertionError, field.to_python, factory.make_string()
        )


class TestCIDRField(MAASLegacyServerTestCase):
    apps = ["maasserver.tests"]

    def test_stores_cidr(self):
        cidr = "192.0.2.0/24"
        instance = CIDRTestModel.objects.create(cidr=cidr)
        self.assertEqual(cidr, reload_object(instance).cidr)

    def test_validates_cidr(self):
        cidr = "invalid-cidr"
        error = self.assertRaises(
            ValidationError, CIDRTestModel.objects.create, cidr=cidr
        )
        self.assertEqual(["invalid IPNetwork %s" % cidr], error.messages)

    def test_stores_cidr_with_bit_set_in_host_part(self):
        cidr = "192.0.2.1/24"
        normalized_cidr = "192.0.2.0/24"
        instance = CIDRTestModel.objects.create(cidr=cidr)
        self.assertEqual(normalized_cidr, reload_object(instance).cidr)


class TestIPv4CIDRField(MAASLegacyServerTestCase):
    apps = ["maasserver.tests"]

    def test_stores_cidr(self):
        cidr = "192.0.2.0/24"
        instance = IPv4CIDRTestModel.objects.create(cidr=cidr)
        self.assertEqual(cidr, reload_object(instance).cidr)

    def test_validates_cidr(self):
        cidr = "invalid-cidr"
        error = self.assertRaises(
            ValidationError, IPv4CIDRTestModel.objects.create, cidr=cidr
        )
        self.assertEqual(["Invalid network: %s" % cidr], error.messages)

    def test_stores_cidr_with_bit_set_in_host_part(self):
        cidr = "192.0.2.1/24"
        normalized_cidr = "192.0.2.0/24"
        instance = IPv4CIDRTestModel.objects.create(cidr=cidr)
        self.assertEqual(normalized_cidr, reload_object(instance).cidr)

    def test_fails_to_store_ipv6_cidr(self):
        cidr = "2001:DB8::/32"
        error = self.assertRaises(
            ValidationError, IPv4CIDRTestModel.objects.create, cidr=cidr
        )
        self.assertEqual(
            ["2001:DB8::/32: Only IPv4 networks supported."], error.messages
        )
