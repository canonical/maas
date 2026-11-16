# Copyright 2012-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test custom field types."""

from base64 import b64encode

from maasserver.testing.testcase import MAASServerTestCase
from maastesting.factory import factory
from metadataserver.fields import Bin


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
