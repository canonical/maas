# Copyright 2012-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

import json

import yaml

from maasserver.api.doc_oapi import endpoint, landing_page
from maasserver.models.config import Config
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maastesting.testcase import MAASTestCase


class TestLandingPage(MAASTestCase):
    def test_links(self):
        request = factory.make_fake_request()
        page = landing_page(request)
        content = json.loads(page.content)
        resources = content["resources"]
        host = request.get_host()
        for link in resources:
            href = f"http://{host}{link['path']}"
            self.assertEqual(link["href"], href)
        self.assertEqual(resources[0]["type"], page["content-type"])


class TestApiEndpoint(MAASServerTestCase):
    def test_required_fields(self):
        request = factory.make_fake_request()
        page = endpoint(request)
        content = yaml.safe_load(page.content)
        self.assertIn("openapi", content)
        self.assertIn("info", content)
        self.assertIn("paths", content)
        info = content["info"]
        self.assertIsInstance(info, dict)
        self.assertIn("title", info)
        self.assertIn("version", info)

    def test_discovered_servers(self):
        request = factory.make_fake_request()
        page = endpoint(request)
        content = yaml.safe_load(page.content)
        self.assertIn("servers", content)
        servers = content["servers"]
        self.assertIsInstance(servers, list)
        maasserver = servers[0]
        maas_name = Config.objects.get_config("maas_name")
        self.assertEqual(
            maasserver["url"], "http://localhost:5240/MAAS/api/2.0/"
        )
        self.assertEqual(maasserver["description"], f"{maas_name} API")
