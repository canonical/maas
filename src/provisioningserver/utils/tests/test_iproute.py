# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

import json

from maastesting.testcase import MAASTestCase
from provisioningserver.utils import iproute as iproute_module
from provisioningserver.utils.iproute import get_ip_route


class TestGetIPRoute(MAASTestCase):
    def test_parse_routes(self):
        routes = [
            {
                "dst": "default",
                "gateway": "10.10.10.1",
                "dev": "eth0",
                "protocol": "dhcp",
                "metric": 600,
                "flags": [],
            },
            {
                "dst": "192.168.1.0/24",
                "gateway": "192.168.1.1",
                "dev": "eth1",
                "protocol": "static",
                "metric": 100,
                "flags": [],
            },
        ]
        patch_call_and_check = self.patch(iproute_module, "call_and_check")
        patch_call_and_check.return_value = json.dumps(routes)
        self.assertEqual(
            get_ip_route(),
            {
                "default": {
                    "gateway": "10.10.10.1",
                    "dev": "eth0",
                    "protocol": "dhcp",
                    "metric": 600,
                    "flags": [],
                },
                "192.168.1.0/24": {
                    "gateway": "192.168.1.1",
                    "dev": "eth1",
                    "protocol": "static",
                    "metric": 100,
                    "flags": [],
                },
            },
        )
        patch_call_and_check.assert_called_once_with(
            ["ip", "-json", "route", "list", "scope", "global"]
        )
