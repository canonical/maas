# Copyright 2024 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

import subprocess

from maasserver.regiondservices import temporal
from maasserver.testing.testcase import MAASTestCase


class TestRegionTemporalServer(MAASTestCase):
    def test_get_broadcast_address(self):
        self.patch(subprocess, "getoutput").return_value = (
            "local 127.0.0.1 dev lo table local src 127.0.0.1 uid 1000 \n    cache <local>"
        )

        service = temporal.RegionTemporalService()

        address = service.get_broadcast_address("http://127.0.0.1:5240/MAAS")
        self.assertEqual(address, "127.0.0.1")
