# Copyright 2012-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test custom field types.

Legacy-tagged (`MAASLegacyTransactionServerTestCase`): these classes
need a Django-migrate test DB and run in the dedicated region-legacy
pytest leg (`MAAS_PREVENT_MIGRATIONS=1`, see utilities/run-py-tests-ci).
The gap-free `TestBin` class has already been relocated to
`src/tests/metadataserver/test_fields.py`.
"""

from maasserver.testing.testcase import MAASLegacyTransactionServerTestCase
from metadataserver.fields import Bin, BinaryField
from metadataserver.tests.models import BinaryFieldModel


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
        binary_item.save()
        self.assertEqual(
            Bin(b""),
            BinaryFieldModel.objects.get(id=binary_item.id).data,
        )

    def test_does_not_truncate_at_zero_bytes(self):
        data = b"BEFORE THE ZERO\x00AFTER THE ZERO"
        binary_item = BinaryFieldModel(data=Bin(data))
        binary_item.save()
        self.assertEqual(
            data,
            BinaryFieldModel.objects.get(id=binary_item.id).data,
        )

    def test_stores_and_retrieves_binary_data(self):
        data = b"\x01\x02\xff\xff\xfe\xff\xff\xfe"
        binary_item = BinaryFieldModel(data=Bin(data))
        binary_item.save()
        self.assertEqual(
            data,
            BinaryFieldModel.objects.get(id=binary_item.id).data,
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
            binary_item,
            BinaryFieldModel.objects.get(data=Bin(data)),
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
