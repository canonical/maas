# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for :py:module:`~maasserver.rpc.configuration`."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

from urlparse import urlparse

from maasserver.models.config import Config
from maasserver.rpc.configuration import get_proxies
from maastesting.factory import factory
from maastesting.testcase import MAASTestCase


class TestGetProxies(MAASTestCase):

    def test_returns_populated_dict_when_http_proxy_is_not_set(self):
        Config.objects.set_config("http_proxy", None)
        self.assertEqual(
            {"http": None, "https": None},
            get_proxies())

    def test_returns_populated_dict_when_http_proxy_is_set(self):
        url = factory.make_parsed_url().geturl()
        Config.objects.set_config("http_proxy", url)
        self.assertEqual(
            {"http": urlparse(url), "https": urlparse(url)},
            get_proxies())
