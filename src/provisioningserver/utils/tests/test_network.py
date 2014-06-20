# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for network helpers."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

from maastesting.testcase import MAASTestCase
import mock
from netaddr import IPNetwork
from provisioningserver.utils import network as network_module
from provisioningserver.utils.network import make_network


class TestMakeNetwork(MAASTestCase):

    def test_constructs_IPNetwork(self):
        network = make_network('10.22.82.0', 24)
        self.assertIsInstance(network, IPNetwork)
        self.assertEqual(IPNetwork('10.22.82.0/24'), network)

    def test_passes_args_to_IPNetwork(self):
        self.patch(network_module, 'IPNetwork')
        make_network('10.1.2.0', 24, foo=9)
        self.assertEqual(
            [mock.call('10.1.2.0/24', foo=9)],
            network_module.IPNetwork.mock_calls)
