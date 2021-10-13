# Copyright 2016-2018 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for the proxyconfig."""


from pathlib import Path
import random

from crochet import wait_for
from django.conf import settings
from fixtures import EnvironmentVariableFixture
from testtools.matchers import Contains, FileContains, Not
from twisted.internet.defer import inlineCallbacks

from maasserver import proxyconfig
from maasserver.models import Config
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASTransactionServerTestCase
from maasserver.utils.orm import transactional
from maasserver.utils.threads import deferToDatabase
from maastesting.matchers import MockCalledOnceWith, MockNotCalled
from provisioningserver.proxy import config
from provisioningserver.utils import snap

wait_for_reactor = wait_for(30)  # 30 seconds.


class TestProxyUpdateConfig(MAASTransactionServerTestCase):
    """Tests for `maasserver.proxyconfig`."""

    def setUp(self):
        super().setUp()
        self.tmpdir = self.make_dir()
        self.proxy_path = Path(self.tmpdir) / config.MAAS_PROXY_CONF_NAME
        self.service_monitor = self.patch(proxyconfig, "service_monitor")
        self.useFixture(
            EnvironmentVariableFixture("MAAS_PROXY_CONFIG_DIR", self.tmpdir)
        )

    @transactional
    def make_subnet(self, allow_proxy=True):
        return factory.make_Subnet(allow_proxy=allow_proxy)

    @wait_for_reactor
    @inlineCallbacks
    def test_only_enabled_subnets_are_present(self):
        self.patch(settings, "PROXY_CONNECT", True)
        disabled = yield deferToDatabase(self.make_subnet, allow_proxy=False)
        enabled = yield deferToDatabase(self.make_subnet)
        yield proxyconfig.proxy_update_config(reload_proxy=False)
        # enabled's cidr must be present
        matcher = Contains("acl localnet src %s" % enabled.cidr)
        self.assertThat(
            "%s/%s" % (self.tmpdir, config.MAAS_PROXY_CONF_NAME),
            FileContains(matcher=matcher),
        )
        # disabled's cidr must not be present
        matcher = Not(Contains("acl localnet src %s" % disabled.cidr))
        self.assertThat(
            "%s/%s" % (self.tmpdir, config.MAAS_PROXY_CONF_NAME),
            FileContains(matcher=matcher),
        )

    @wait_for_reactor
    @inlineCallbacks
    def test_with_use_peer_proxy_with_http_proxy(self):
        self.patch(settings, "PROXY_CONNECT", True)
        yield deferToDatabase(
            transactional(Config.objects.set_config), "enable_http_proxy", True
        )
        yield deferToDatabase(
            transactional(Config.objects.set_config), "use_peer_proxy", True
        )
        yield deferToDatabase(
            transactional(Config.objects.set_config),
            "http_proxy",
            "http://example.com:8000/",
        )
        yield deferToDatabase(self.make_subnet, allow_proxy=False)
        yield deferToDatabase(self.make_subnet)
        yield proxyconfig.proxy_update_config(reload_proxy=False)
        cache_peer_line = (
            "cache_peer example.com parent 8000 0 no-query default"
        )
        with self.proxy_path.open() as proxy_file:
            lines = [line.strip() for line in proxy_file.readlines()]
            self.assertIn("never_direct allow all", lines)
            self.assertIn(cache_peer_line, lines)

    @wait_for_reactor
    @inlineCallbacks
    def test_with_use_peer_proxy_without_http_proxy(self):
        self.patch(settings, "PROXY_CONNECT", True)
        yield deferToDatabase(
            transactional(Config.objects.set_config), "enable_http_proxy", True
        )
        yield deferToDatabase(
            transactional(Config.objects.set_config), "use_peer_proxy", True
        )
        yield deferToDatabase(
            transactional(Config.objects.set_config), "http_proxy", ""
        )
        yield deferToDatabase(self.make_subnet, allow_proxy=False)
        yield deferToDatabase(self.make_subnet)
        yield proxyconfig.proxy_update_config(reload_proxy=False)
        with self.proxy_path.open() as proxy_file:
            lines = [line.strip() for line in proxy_file.readlines()]
            self.assertNotIn("never_direct allow all", lines)
            self.assertNotIn("cache_peer", lines)

    @wait_for_reactor
    @inlineCallbacks
    def test_without_use_peer_proxy(self):
        self.patch(settings, "PROXY_CONNECT", True)
        yield deferToDatabase(
            transactional(Config.objects.set_config), "enable_http_proxy", True
        )
        yield deferToDatabase(
            transactional(Config.objects.set_config), "use_peer_proxy", False
        )
        yield deferToDatabase(
            transactional(Config.objects.set_config),
            "http_proxy",
            "http://example.com:8000/",
        )
        yield deferToDatabase(self.make_subnet, allow_proxy=False)
        yield deferToDatabase(self.make_subnet)
        yield proxyconfig.proxy_update_config(reload_proxy=False)
        with self.proxy_path.open() as proxy_file:
            lines = [line.strip() for line in proxy_file.readlines()]
            self.assertNotIn("never_direct allow all", lines)
            self.assertNotIn("cache_peer", lines)

    @wait_for_reactor
    @inlineCallbacks
    def test_with_prefer_v4_proxy_False(self):
        self.patch(settings, "PROXY_CONNECT", True)
        yield deferToDatabase(
            transactional(Config.objects.set_config), "prefer_v4_proxy", False
        )
        yield proxyconfig.proxy_update_config(reload_proxy=False)
        with self.proxy_path.open() as proxy_file:
            lines = [line.strip() for line in proxy_file.readlines()]
            self.assertNotIn("dns_v4_first on", lines)

    @wait_for_reactor
    @inlineCallbacks
    def test_with_prefer_v4_proxy_True(self):
        self.patch(settings, "PROXY_CONNECT", True)
        yield deferToDatabase(
            transactional(Config.objects.set_config), "prefer_v4_proxy", True
        )
        yield proxyconfig.proxy_update_config(reload_proxy=False)
        with self.proxy_path.open() as proxy_file:
            lines = [line.strip() for line in proxy_file.readlines()]
            self.assertIn("dns_v4_first on", lines)

    @wait_for_reactor
    @inlineCallbacks
    def test_with_new_maas_proxy_port_changes_port(self):
        self.patch(settings, "PROXY_CONNECT", True)
        port = random.randint(1, 65535)
        yield deferToDatabase(
            transactional(Config.objects.set_config), "maas_proxy_port", port
        )
        yield proxyconfig.proxy_update_config(reload_proxy=False)
        with self.proxy_path.open() as proxy_file:
            lines = [line.strip() for line in proxy_file.readlines()]
            self.assertIn("http_port %s" % port, lines)

    @wait_for_reactor
    @inlineCallbacks
    def test_calls_reloadService(self):
        self.patch(settings, "PROXY_CONNECT", True)
        yield deferToDatabase(self.make_subnet)
        yield proxyconfig.proxy_update_config()
        self.assertThat(
            self.service_monitor.reloadService,
            MockCalledOnceWith("proxy", if_on=True),
        )

    @wait_for_reactor
    @inlineCallbacks
    def test_calls_restartService(self):
        self.patch(settings, "PROXY_CONNECT", True)
        self.patch(snap, "running_in_snap").return_value = True
        yield deferToDatabase(self.make_subnet)
        yield proxyconfig.proxy_update_config()
        self.assertThat(
            self.service_monitor.restartService,
            MockCalledOnceWith("proxy", if_on=True),
        )

    @wait_for_reactor
    @inlineCallbacks
    def test_doesnt_call_reloadService_when_PROXY_CONNECT_False(self):
        self.patch(settings, "PROXY_CONNECT", False)
        yield deferToDatabase(self.make_subnet)
        yield proxyconfig.proxy_update_config()
        self.assertThat(self.service_monitor.reloadService, MockNotCalled())

    @wait_for_reactor
    @inlineCallbacks
    def test_doesnt_call_reloadService_when_reload_proxy_False(self):
        self.patch(settings, "PROXY_CONNECT", True)
        yield deferToDatabase(self.make_subnet)
        yield proxyconfig.proxy_update_config(reload_proxy=False)
        self.assertThat(self.service_monitor.reloadService, MockNotCalled())
