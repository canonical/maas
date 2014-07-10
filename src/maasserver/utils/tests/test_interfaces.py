# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for network/cluster interface helpers."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

from maasserver.utils.interfaces import make_name_from_interface
from maastesting.factory import factory
from maastesting.testcase import MAASTestCase


class TestMakeNameFromInterface(MAASTestCase):
    """Tests for `make_name_from_interface`."""

    def test__passes_name_unchanged(self):
        name = factory.make_name('itf9:2')
        self.assertEqual(name, make_name_from_interface(name))

    def test__escapes_weird_characters(self):
        self.assertEqual('x--y', make_name_from_interface('x?y'))
        self.assertEqual('x--y', make_name_from_interface('x y'))

    def test__makes_up_name_if_no_interface_given(self):
        self.assertNotIn(make_name_from_interface(None), (None, ''))
        self.assertNotIn(make_name_from_interface(''), (None, ''))

    def test__makes_up_unique_name_if_no_interface_given(self):
        self.assertNotEqual(
            make_name_from_interface(''),
            make_name_from_interface(''))
