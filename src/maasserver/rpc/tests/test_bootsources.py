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
from maastesting.testcase import MAASTestCase


class TestGetBootSources(MAASTestCase):

    def test_returns_empty_list_when_cluster_does_not_exist(self):
        uuid = factory.make_UUID()
        self.assertEqual([], get_boot_sources(uuid))

    def test_returns_boot_sources_and_selections(self):
        keyring = factory.make_bytes()
        nodegroup = factory.make_node_group()
        source = factory.make_boot_source(nodegroup, keyring_data=keyring)
        factory.make_boot_source_selection(source)

        expected = source.to_dict()
        # To the cluster there's no distinction between the keyring file
        # and keyring data, so it's passed as keyring.
        expected["keyring"] = keyring
        del expected["keyring_data"]

        self.assertEqual([expected], get_boot_sources(nodegroup.uuid))
