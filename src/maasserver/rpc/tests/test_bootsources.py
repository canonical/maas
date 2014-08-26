# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for :py:module:`~maasserver.rpc.bootsources`."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

from maasserver.rpc.bootsources import get_boot_sources
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase


class TestGetBootSources(MAASServerTestCase):

    def test_returns_boot_sources_and_selections(self):
        keyring = factory.make_bytes()
        nodegroup = factory.make_node_group()
        source = factory.make_boot_source(keyring_data=keyring)
        factory.make_boot_source_selection(source)

        expected = source.to_dict()
        self.assertEqual([expected], get_boot_sources(nodegroup.uuid))

    def test_removes_os_from_boot_source_selections(self):
        keyring = factory.make_bytes()
        nodegroup = factory.make_node_group()
        source = factory.make_boot_source(keyring_data=keyring)
        factory.make_boot_source_selection(source)

        expected = source.to_dict()
        del expected['selections'][0]['os']
        self.assertEqual(
            [expected], get_boot_sources(nodegroup.uuid, remove_os=True))
