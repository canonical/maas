# Copyright 2022 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test OpenApi commands work correctly."""

from io import StringIO

from django.core.management import call_command
import yaml

from maasserver.api.doc_oapi import get_api_endpoint
from maasserver.testing.testcase import MAASServerTestCase


class TestOAPIDoc(MAASServerTestCase):
    def test_generate_spec(self):
        spec = get_api_endpoint()
        spec["externalDocs"]["url"] = "https://maas.io/docs"
        out = StringIO()
        call_command("generate_oapi_spec", stdout=out)
        self.assertEqual(yaml.dump(spec), out.getvalue())
