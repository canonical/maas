# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for the top-level cluster RPC API."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
]

from maastesting.testcase import MAASTestCase
import provisioningserver


class TestFunctions(MAASTestCase):

    def test_get_rpc_client_returns_client(self):
        services = self.patch(provisioningserver, "services")

        client = provisioningserver.rpc.getRegionClient()
        self.assertEqual(
            services.getServiceNamed('rpc').getClient(),
            client,
        )
