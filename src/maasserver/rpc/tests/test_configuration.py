# Copyright 2014-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for :py:module:`~maasserver.rpc.configuration`."""


from urllib.parse import urlparse

from maasserver.models.config import Config
from maasserver.models.signals import bootsources
from maasserver.rpc.configuration import get_proxies
from maasserver.testing.testcase import MAASServerTestCase
from maastesting.factory import factory


class TestGetProxies(MAASServerTestCase):
    def setUp(self):
        super().setUp()
        # Disable boot source cache signals.
        self.addCleanup(bootsources.signals.enable)
        bootsources.signals.disable()

    def test_returns_populated_dict_when_http_proxy_is_not_set(self):
        Config.objects.set_config("enable_http_proxy", True)
        Config.objects.set_config("http_proxy", None)
        self.assertEqual({"http": None, "https": None}, get_proxies())

    def test_returns_populated_dict_when_http_proxy_is_set(self):
        Config.objects.set_config("enable_http_proxy", True)
        url = factory.make_parsed_url().geturl()
        Config.objects.set_config("http_proxy", url)
        self.assertEqual(
            {"http": urlparse(url), "https": urlparse(url)}, get_proxies()
        )

    def test_returns_populated_dict_when_http_proxy_is_disabled(self):
        Config.objects.set_config("enable_http_proxy", False)
        url = factory.make_parsed_url().geturl()
        Config.objects.set_config("http_proxy", url)
        self.assertEqual({"http": None, "https": None}, get_proxies())
