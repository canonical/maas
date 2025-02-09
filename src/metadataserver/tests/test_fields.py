# Copyright 2012-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test custom field types."""

from base64 import b64encode

from maasserver.testing.testcase import (
    MAASLegacyTransactionServerTestCase,
    MAASServerTestCase,
)
from maastesting.factory import factory
from metadataserver.fields import Bin, BinaryField
from metadataserver.tests.models import BinaryFieldModel


class TestBin(MAASServerTestCase):
    """Test Bin helper class."""

    def test_is_basically_bytes(self):
        self.assertEqual(b"Hello", Bin(b"Hello"))

    def test_refuses_to_construct_from_unicode(self):
        self.assertRaises(AssertionError, Bin, "Hello")

    def test_refuses_to_construct_from_None(self):
        self.assertRaises(AssertionError, Bin, None)

    def test_emits_base64(self):
        # Piston hooks onto an __emittable__() method, if present.
        # Bin() returns a base-64 encoded string so that it can be
        # transmitted in JSON.
        self.assertEqual("", Bin(b"").__emittable__())
        example_bytes = factory.make_bytes()
        self.assertEqual(
            b64encode(example_bytes).decode("ascii"),
            Bin(example_bytes).__emittable__(),
        )


class TestBinaryField(MAASLegacyTransactionServerTestCase):
    """Test BinaryField.  Uses BinaryFieldModel test model."""

    apps = ["metadataserver.tests"]

    def test_stores_and_retrieves_None(self):
        binary_item = BinaryFieldModel()
        self.assertIsNone(binary_item.data)
        binary_item.save()
        self.assertIsNone(BinaryFieldModel.objects.get(id=binary_item.id).data)

    def test_stores_and_retrieves_empty_data(self):
        binary_item = BinaryFieldModel(data=Bin(b""))
        self.assertEqual(b"", binary_item.data)
        binary_item.save()
        self.assertEqual(
            b"", BinaryFieldModel.objects.get(id=binary_item.id).data
        )

    def test_does_not_truncate_at_zero_bytes(self):
        data = b"BEFORE THE ZERO\x00AFTER THE ZERO"
        binary_item = BinaryFieldModel(data=Bin(data))
        self.assertEqual(data, binary_item.data)
        binary_item.save()
        self.assertEqual(
            data, BinaryFieldModel.objects.get(id=binary_item.id).data
        )

    def test_stores_and_retrieves_binary_data(self):
        data = b"\x01\x02\xff\xff\xfe\xff\xff\xfe"
        binary_item = BinaryFieldModel(data=Bin(data))
        self.assertEqual(data, binary_item.data)
        binary_item.save()
        self.assertEqual(
            data, BinaryFieldModel.objects.get(id=binary_item.id).data
        )

    def test_returns_bytes_not_text(self):
        binary_item = BinaryFieldModel(data=Bin(b"Data"))
        binary_item.save()
        retrieved_data = BinaryFieldModel.objects.get(id=binary_item.id).data
        self.assertIsInstance(retrieved_data, bytes)

    def test_looks_up_data(self):
        data = b"Binary item"
        binary_item = BinaryFieldModel(data=Bin(data))
        binary_item.save()
        self.assertEqual(
            binary_item, BinaryFieldModel.objects.get(data=Bin(data))
        )

    def test_get_default_returns_None(self):
        field = BinaryField(null=True)
        self.patch(field, "default", None)
        self.assertIsNone(field.get_default())

    def test_get_default_returns_Bin(self):
        field = BinaryField(null=True)
        self.patch(field, "default", Bin(b"wotcha"))
        self.assertEqual(Bin(b"wotcha"), field.get_default())

    def test_get_default_returns_Bin_from_bytes(self):
        field = BinaryField(null=True)
        self.patch(field, "default", b"wotcha")
        self.assertEqual(Bin(b"wotcha"), field.get_default())
