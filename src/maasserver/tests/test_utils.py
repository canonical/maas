# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for miscellaneous helpers."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = []

from django.conf import settings
from django.core.urlresolvers import reverse
from maasserver.enum import NODE_STATUS_CHOICES
from maasserver.testing.factory import factory
from maasserver.testing.testcase import TestCase as DjangoTestCase
from maasserver.utils import (
    absolute_reverse,
    get_db_state,
    map_enum,
    )
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


class TestAbsoluteReverse(DjangoTestCase):

    def test_absolute_reverse_uses_DEFAULT_MAAS_URL(self):
        maas_url = 'http://%s' % factory.getRandomString()
        self.patch(settings, 'DEFAULT_MAAS_URL', maas_url)
        absolute_url = absolute_reverse('settings')
        expected_url = settings.DEFAULT_MAAS_URL + reverse('settings')
        self.assertEqual(expected_url, absolute_url)

    def test_absolute_reverse_uses_kwargs(self):
        node = factory.make_node()
        self.patch(settings, 'DEFAULT_MAAS_URL', '')
        absolute_url = absolute_reverse(
            'node-view', kwargs={'system_id': node.system_id})
        expected_url = reverse('node-view', args=[node.system_id])
        self.assertEqual(expected_url, absolute_url)

    def test_absolute_reverse_uses_args(self):
        node = factory.make_node()
        self.patch(settings, 'DEFAULT_MAAS_URL', '')
        absolute_url = absolute_reverse('node-view', args=[node.system_id])
        expected_url = reverse('node-view', args=[node.system_id])
        self.assertEqual(expected_url, absolute_url)


class GetDbStateTest(DjangoTestCase):
    """Testing for the method `get_db_state`."""

    def test_get_db_state_returns_db_state(self):
        status = factory.getRandomChoice(NODE_STATUS_CHOICES)
        node = factory.make_node(status=status)
        another_status = factory.getRandomChoice(
            NODE_STATUS_CHOICES, but_not=[status])
        node.status = another_status
        self.assertEqual(status, get_db_state(node, 'status'))
