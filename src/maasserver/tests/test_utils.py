# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for enumeration helpers."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = []

from maasserver.utils import map_enum
from maastesting.testcase import TestCase


class TestEnum(TestCase):

    def test_map_enum_includes_all_enum_values(self):

        class Enum:
            ONE = 1
            TWO = 2

        self.assertItemsEqual(['ONE', 'TWO'], map_enum(Enum).keys())

    def test_map_enum_omits_private_or_special_methods(self):

        class Enum:
            def __init__(self):
                pass

            def __repr__(self):
                return "Enum"

            def _save(self):
                pass

            VALUE = 9

        self.assertItemsEqual(['VALUE'], map_enum(Enum).keys())

    def test_map_enum_maps_values(self):

        class Enum:
            ONE = 1
            THREE = 3

        self.assertEqual({'ONE': 1, 'THREE': 3}, map_enum(Enum))
