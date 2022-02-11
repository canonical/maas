# Copyright 2022 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

import http.client

from django.urls import reverse

from maasserver.testing.api import APITestCase
from maasserver.testing.factory import factory


class TestMAASRunScriptHandlerFor(APITestCase.ForAnonymous):
    def _get_maas_run_scripts_url(self, arch=None):
        if arch is None:
            return reverse("maas-run-scripts")
        return reverse("maas-run-scripts-bin", args=[arch])

    def test_read_no_architecture_arg_serves_scripts(self):
        response = self.client.get(self._get_maas_run_scripts_url())
        self.assertEqual(http.client.OK, response.status_code)
        self.assertEqual("text/x-python", response["Content-Type"])
        self.assertIn(b"#!/usr/bin/env python3", response.content)

    def test_read_architecture_serves_binary(self):
        node = factory.make_Node()
        response = self.client.get(
            self._get_maas_run_scripts_url(arch=node.architecture)
        )
        self.assertEqual(http.client.FOUND, response.status_code)
        self.assertEqual(
            f"/MAAS/hardware-sync/{node.architecture}", response.url
        )
