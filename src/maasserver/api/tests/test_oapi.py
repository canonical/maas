# Copyright 2012-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

import json

import yaml

from maasserver.api.doc_oapi import (
    _prettify,
    _render_oapi_paths,
    endpoint,
    landing_page,
)
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


class TestOAPISpec(MAASServerTestCase):
    def setUp(self):
        self.oapi_types = ["boolean", "integer", "number", "object", "string"]
        self.oapi_ops = [
            "get",
            "put",
            "post",
            "delete",
            "options",
            "head",
            "patch",
            "trace",
            "servers",
        ]
        return super().setUp()

    def test_paths(self):
        # TODO add actual tests
        _render_oapi_paths()

    def test_path_parameters(self):
        for path in _render_oapi_paths().values():
            if "parameters" not in path:
                continue
            for param in path["parameters"]:
                self.assertIn("name", param)
                self.assertIn("in", param)
                self.assertIn(
                    param["in"], ["cookie", "header", "path", "query"]
                )
                self.assertTrue(param["required"])
                if "schema" in param:
                    self.assertIn(param["schema"]["type"], self.oapi_types)

    def test_path_operations(self):
        for path in _render_oapi_paths().values():
            isct_ops = list(set(self.oapi_ops) & set(path.keys()))
            for op in isct_ops:
                for response in path[op]["responses"].values():
                    self.assertIn("description", response)

    def test_path_object_types(self):
        def _get_all_key_values(d):
            for k, v in d.items():
                if isinstance(v, dict):
                    yield from _get_all_key_values(v)
                else:
                    yield (k, v)

        for k, v in _get_all_key_values(_render_oapi_paths()):
            if k == "type":
                self.assertIn(v, self.oapi_types)


class TestPrettify(MAASTestCase):
    maxDiff = None

    def test_cleans_newlines(self):
        before = """\
Returns system details -- for example, LLDP and

``lshw`` XML dumps.


Returns a ``{detail_type: xml, ...}`` map, where

``detail_type`` is something like "lldp" or "lshw".


Note that this is returned as BSON and not JSON. This is for

efficiency, but mainly because JSON can''t do binary content without

applying additional encoding like base-64. The example output below is

represented in ASCII using ``bsondump example.bson`` and is for

demonstrative purposes."""

        after = """\
Returns system details - for example, LLDP and `lshw` XML dumps.
Returns a `{detail_type: xml, .}` map, where `detail_type` is something like "lldp" or "lshw".
Note that this is returned as BSON and not JSON. This is for efficiency, but mainly because JSON can't do binary content without applying additional encoding like base-64. The example output below is represented in ASCII using `bsondump example.bson` and is for demonstrative purposes."""

        self.assertEqual(_prettify(before), after)
