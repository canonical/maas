# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test forms."""

from __future__ import (
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = []

from django.http import QueryDict
from maasserver.forms import NodeWithMACAddressesForm
from maasserver.testing import TestCase


class NodeWithMACAddressesFormTest(TestCase):

    def get_QueryDict(self, params):
        query_dict = QueryDict('', mutable=True)
        for k, v in params.items():
            if isinstance(v, list):
                query_dict.setlist(k, v)
            else:
                query_dict[k] = v
        return query_dict

    def test_NodeWithMACAddressesForm_valid(self):

        form = NodeWithMACAddressesForm(
            self.get_QueryDict(
                {'macaddresses': ['aa:bb:cc:dd:ee:ff', '9a:bb:c3:33:e5:7f']}))

        self.assertTrue(form.is_valid())
        self.assertEqual(
            ['aa:bb:cc:dd:ee:ff', '9a:bb:c3:33:e5:7f'],
            form.cleaned_data['macaddresses'])

    def test_NodeWithMACAddressesForm_invalid(self):
        form = NodeWithMACAddressesForm(
            self.get_QueryDict(
                {'macaddresses': ['aa:bb:cc:dd:ee:ff', 'z_invalid']}))

        self.assertFalse(form.is_valid())

    def test_NodeWithMACAddressesForm_save(self):
        form = NodeWithMACAddressesForm(
            self.get_QueryDict(
                {'macaddresses': ['aa:bb:cc:dd:ee:ff', '9a:bb:c3:33:e5:7f']}))
        node = form.save()

        self.assertIsNotNone(node.id)  # The node is persisted.
        self.assertSequenceEqual(
            ['aa:bb:cc:dd:ee:ff', '9a:bb:c3:33:e5:7f'],
            [mac.mac_address for mac in node.macaddress_set.all()])
