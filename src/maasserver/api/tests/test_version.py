# Copyright 2014-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).


import http.client
import json

from django.conf import settings
from django.urls import reverse

from maasserver.api.version import API_CAPABILITIES_LIST
from maasserver.models import ControllerInfo
from maasserver.testing.api import APITestCase
from maasserver.testing.factory import factory


class TestVersionAPIBasics(APITestCase.ForAnonymousAndUserAndAdmin):
    """Basic tests for /version/ API."""

    def test_handler_path(self):
        self.assertEqual("/MAAS/api/2.0/version/", reverse("version_handler"))


class TestVersionAPI(APITestCase.ForAnonymousAndUser):
    """Tests for /version/ API."""

    def test_GET_returns_details(self):
        ControllerInfo.objects.set_version(
            factory.make_RegionRackController(), "3.0.0~beta1"
        )

        response = self.client.get(reverse("version_handler"))
        self.assertEqual(http.client.OK, response.status_code)

        parsed_result = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET)
        )
        self.assertEqual(
            {
                "capabilities": API_CAPABILITIES_LIST,
                "version": "3.0.0~beta1",
                "subversion": "",
            },
            parsed_result,
        )
