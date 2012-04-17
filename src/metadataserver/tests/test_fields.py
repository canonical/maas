# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test custom field types."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = []

from maasserver.testing.testcase import (
    TestCase,
    TestModelTestCase,
    )
from metadataserver.fields import Bin
from metadataserver.tests.models import BinaryFieldModel


class TestBin(TestCase):
    """Test Bin helper class."""

    def test_is_basically_str(self):
        self.assertEqual(str(b"Hello"), Bin(b"Hello"))

    def test_refuses_to_construct_from_unicode(self):
        self.assertRaises(AssertionError, Bin, "Hello")

    def test_refuses_to_construct_from_None(self):
        self.assertRaises(AssertionError, Bin, None)


class TestBinaryField(TestModelTestCase):
    """Test BinaryField.  Uses BinaryFieldModel test model."""

    app = 'metadataserver.tests'

    def test_stores_and_retrieves_None(self):
        binary_item = BinaryFieldModel()
        self.assertIsNone(binary_item.data)
        binary_item.save()
        self.assertIsNone(
            BinaryFieldModel.objects.get(id=binary_item.id).data)

    def test_stores_and_retrieves_empty_data(self):
        binary_item = BinaryFieldModel(data=Bin(b''))
        self.assertEqual(b'', binary_item.data)
        binary_item.save()
        self.assertEqual(
            b'', BinaryFieldModel.objects.get(id=binary_item.id).data)

    def test_does_not_truncate_at_zero_bytes(self):
        data = b"BEFORE THE ZERO\x00AFTER THE ZERO"
        binary_item = BinaryFieldModel(data=Bin(data))
        self.assertEqual(data, binary_item.data)
        binary_item.save()
        self.assertEqual(
            data, BinaryFieldModel.objects.get(id=binary_item.id).data)

    def test_stores_and_retrieves_binary_data(self):
        data = b"\x01\x02\xff\xff\xfe\xff\xff\xfe"
        binary_item = BinaryFieldModel(data=Bin(data))
        self.assertEqual(data, binary_item.data)
        binary_item.save()
        self.assertEqual(
            data, BinaryFieldModel.objects.get(id=binary_item.id).data)

    def test_returns_bytes_not_text(self):
        binary_item = BinaryFieldModel(data=Bin(b"Data"))
        binary_item.save()
        retrieved_data = BinaryFieldModel.objects.get(id=binary_item.id).data
        self.assertIsInstance(retrieved_data, str)

    def test_looks_up_data(self):
        data = b"Binary item"
        binary_item = BinaryFieldModel(data=Bin(data))
        binary_item.save()
        self.assertEqual(
            binary_item, BinaryFieldModel.objects.get(data=Bin(data)))
