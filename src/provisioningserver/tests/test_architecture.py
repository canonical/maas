# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `list_supported_architectures`."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

from maastesting.factory import factory
from maastesting.testcase import MAASTestCase
from provisioningserver import architecture


class TestListSupportedArchitectures(MAASTestCase):

    def test_lists_architectures_with_subarchitectures(self):
        architectures = architecture.list_supported_architectures()
        self.assertIsInstance(architectures, list)
        self.assertIn('i386/generic', architectures)

    def test_sorts_results(self):
        self.patch(
            architecture, 'ARCHITECTURES',
            [factory.make_name('arch') for _ in range(3)])
        self.assertEqual(
            sorted(architecture.ARCHITECTURES),
            architecture.list_supported_architectures())
