# Copyright 2015-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for maas endpoint in the API."""

__all__ = []

import http.client
import json
from operator import itemgetter

from django.conf import settings
from django.core.urlresolvers import reverse
from maasserver.forms_settings import CONFIG_ITEMS_KEYS
from maasserver.models.config import (
    Config,
    DEFAULT_CONFIG,
)
from maasserver.testing.api import APITestCase
from maasserver.testing.factory import factory
from maasserver.testing.osystems import (
    make_osystem_with_releases,
    make_usable_osystem,
    patch_usable_osystems,
)
from maastesting.matchers import DocTestMatches
from maastesting.testcase import MAASTestCase
from testtools.content import text_content
from testtools.matchers import (
    AfterPreprocessing,
    Equals,
    MatchesAll,
    MatchesDict,
    MatchesListwise,
    MatchesStructure,
)

# Names forbidden for use via the Web API.
FORBIDDEN_NAMES = {
    "omapi_key", "rpc_region_certificate",
    "rpc_shared_secret", "commissioning_osystem",
}


class TestForbiddenNames(MAASTestCase):

    def test_forbidden_names(self):
        # The difference between the set of possible configuration keys and
        # those permitted via the Web API is small but important to security.
        self.assertThat(
            set(DEFAULT_CONFIG).difference(CONFIG_ITEMS_KEYS),
            Equals(FORBIDDEN_NAMES))


class MAASHandlerAPITest(APITestCase.ForUser):

    def test_get_config_default_distro_series(self):
        default_distro_series = factory.make_name("distro_series")
        Config.objects.set_config(
            "default_distro_series", default_distro_series)
        response = self.client.get(
            reverse('maas_handler'), {
                "op": "get_config",
                "name": "default_distro_series",
            })
        self.assertEqual(
            http.client.OK, response.status_code, response.content)
        expected = '"%s"' % default_distro_series
        self.assertEqual(
            expected.encode(settings.DEFAULT_CHARSET), response.content)

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
        self.assertEqual(
            http.client.OK, response.status_code, response.content)
        self.assertEqual(
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
        self.assertEqual(
            http.client.BAD_REQUEST, response.status_code, response.content)

    def assertInvalidConfigurationSetting(self, name, response):
        self.addDetail(
            "Response for op={get,set}_config&name=%s" % name, text_content(
                response.serialize().decode(settings.DEFAULT_CHARSET)))
        self.expectThat(
            response, MatchesAll(
                # An HTTP 400 response,
                MatchesStructure(
                    status_code=Equals(http.client.BAD_REQUEST)),
                # with a JSON body,
                AfterPreprocessing(
                    itemgetter("Content-Type"),
                    Equals("application/json")),
                # containing a serialised ValidationError.
                AfterPreprocessing(
                    lambda response: json.loads(
                        response.content.decode(settings.DEFAULT_CHARSET)),
                    MatchesDict({
                        name: MatchesListwise([
                            DocTestMatches(
                                name + " is not a valid config setting "
                                "(valid settings are: ...)."),
                        ]),
                    })),
                first_only=True,
            ))

    def test_get_config_forbidden_config_items(self):
        for name in FORBIDDEN_NAMES:
            response = self.client.get(
                reverse('maas_handler'), {
                    "op": "get_config", "name": name,
                })
            self.assertInvalidConfigurationSetting(name, response)

    def test_set_config_forbidden_config_items(self):
        self.become_admin()
        for name in FORBIDDEN_NAMES:
            response = self.client.post(
                reverse('maas_handler'), {
                    "op": "set_config", "name": name,
                    "value": factory.make_name("nonsense"),
                })
            self.assertInvalidConfigurationSetting(name, response)
