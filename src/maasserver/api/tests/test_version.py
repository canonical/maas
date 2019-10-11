# Copyright 2014-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test maasserver API version."""

__all__ = []


import http.client
import json

from django.conf import settings
from maasserver.api.version import API_CAPABILITIES_LIST
from maasserver.testing.api import APITestCase
from maasserver.utils.django_urls import reverse
from provisioningserver.utils import version as version_module


class TestVersionAPIBasics(APITestCase.ForAnonymousAndUserAndAdmin):
    """Basic tests for /version/ API."""

    def test_handler_path(self):
        self.assertEqual("/MAAS/api/2.0/version/", reverse("version_handler"))


class TestVersionAPI(APITestCase.ForAnonymousAndUser):
    """Tests for /version/ API."""

    def test_GET_returns_details(self):
        mock_apt = self.patch(version_module, "get_version_from_apt")
        mock_apt.return_value = "1.8.0~alpha4+bzr356-0ubuntu1"
        version_module.get_maas_version.cache_clear()
        version_module.get_maas_version_subversion.cache_clear()

        response = self.client.get(reverse("version_handler"))
        self.assertEqual(http.client.OK, response.status_code)

        parsed_result = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET)
        )
        self.assertEqual(
            {
                "capabilities": API_CAPABILITIES_LIST,
                "version": "1.8.0~alpha4",
                "subversion": "bzr356-0ubuntu1",
            },
            parsed_result,
        )
