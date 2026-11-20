# Copyright 2014-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for the top-level cluster RPC API."""

from maastesting.testcase import MAASTestCase
import provisioningserver
from provisioningserver.rpc.exceptions import NoConnectionsAvailable


class TestUtilities(MAASTestCase):
    def test_get_rpc_client_returns_client(self):
        services = self.patch(provisioningserver, "services")

        client = provisioningserver.rpc.getRegionClient()
        self.assertEqual(services.getServiceNamed("rpc").getClient(), client)

    def test_error_when_cluster_services_are_down(self):
        services = self.patch(provisioningserver, "services")
        services.getServiceNamed.side_effect = KeyError
        self.assertRaises(
            NoConnectionsAvailable, provisioningserver.rpc.getRegionClient
        )
