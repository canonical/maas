# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for maas endpoint in the API."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

import httplib

from django.core.urlresolvers import reverse
from maasserver.models.config import Config
from maasserver.testing.api import APITestCase
from maasserver.testing.factory import factory
from maasserver.testing.osystems import (
    make_osystem_with_releases,
    make_usable_osystem,
    patch_usable_osystems,
)


class MAASHandlerAPITest(APITestCase):

    def test_get_config_default_distro_series(self):
        self.become_admin()
        default_distro_series = factory.make_name("distro_series")
        Config.objects.set_config(
            "default_distro_series", default_distro_series)
        response = self.client.get(
            reverse('maas_handler'), {
                "op": "get_config",
                "name": "default_distro_series",
            })
        self.assertEquals(httplib.OK, response.status_code, response.content)
        self.assertEquals('"%s"' % default_distro_series, response.content)

    def test_set_config_default_distro_series(self):
        self.become_admin()
        osystem = make_usable_osystem(self)
        Config.objects.set_config("default_osystem", osystem['name'])
        selected_release = osystem['releases'][0]['name']
        response = self.client.post(
            reverse('maas_handler'), {
                "op": "set_config",
                "name": "default_distro_series",
                "value": selected_release,
            })
        self.assertEquals(httplib.OK, response.status_code, response.content)
        self.assertEquals(
            selected_release,
            Config.objects.get_config("default_distro_series"))

    def test_set_config_only_default_osystem_are_valid_for_distro_series(self):
        self.become_admin()
        default_osystem = make_osystem_with_releases(self)
        other_osystem = make_osystem_with_releases(self)
        patch_usable_osystems(self, [default_osystem, other_osystem])
        Config.objects.set_config("default_osystem", default_osystem['name'])
        invalid_release = other_osystem['releases'][0]['name']
        response = self.client.post(
            reverse('maas_handler'), {
                "op": "set_config",
                "name": "default_distro_series",
                "value": invalid_release,
            })
        self.assertEquals(
            httplib.BAD_REQUEST, response.status_code, response.content)
