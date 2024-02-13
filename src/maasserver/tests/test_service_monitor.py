# Copyright 2016-2022 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).


import os

from twisted.internet.defer import inlineCallbacks, maybeDeferred

from maasserver.models.config import Config
from maasserver.models.signals import bootsources
from maasserver.service_monitor import ProxyService, service_monitor
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASTransactionServerTestCase
from maasserver.utils.orm import transactional
from maasserver.utils.threads import deferToDatabase
from maastesting.crochet import wait_for
from maastesting.testcase import MAASTestCase
from provisioningserver.proxy import config
from provisioningserver.utils.service_monitor import SERVICE_STATE

wait_for_reactor = wait_for()


class TestGlobalServiceMonitor(MAASTestCase):
    def test_includes_all_services(self):
        self.assertEqual(
            {
                "bind9",
                "ntp_region",
                "proxy",
                "reverse_proxy",
                "syslog_region",
                "temporal",
                "temporal-worker",
            },
            service_monitor._services.keys(),
        )


class TestProxyService(MAASTransactionServerTestCase):
    def setUp(self):
        super().setUp()
        self.addCleanup(bootsources.signals.enable)
        bootsources.signals.disable()

    def make_proxy_service(self):
        class FakeProxyService(ProxyService):
            name = factory.make_name("name")
            service_name = factory.make_name("service")

        return FakeProxyService()

    @wait_for_reactor
    @inlineCallbacks
    def test_getExpectedState_returns_off_for_proxy_off_and_unset(self):
        service = self.make_proxy_service()
        yield deferToDatabase(
            transactional(Config.objects.set_config),
            "enable_http_proxy",
            False,
        )
        self.patch(config, "is_config_present").return_value = True
        expected_state = yield maybeDeferred(service.getExpectedState)
        self.assertEqual(
            (SERVICE_STATE.OFF, "proxy disabled."), expected_state
        )

    @wait_for_reactor
    @inlineCallbacks
    def test_getExpectedState_returns_off_for_no_config(self):
        yield deferToDatabase(
            transactional(Config.objects.set_config),
            "enable_http_proxy",
            True,
        )
        service = self.make_proxy_service()
        os.environ["MAAS_PROXY_CONFIG_DIR"] = "/tmp/%s" % factory.make_name()
        expected_state = yield maybeDeferred(service.getExpectedState)
        self.assertEqual(
            (SERVICE_STATE.OFF, "no configuration file present."),
            expected_state,
        )
        del os.environ["MAAS_PROXY_CONFIG_DIR"]

    @wait_for_reactor
    @inlineCallbacks
    def test_getExpectedState_returns_off_for_proxy_off_and_set(self):
        service = self.make_proxy_service()
        yield deferToDatabase(
            transactional(Config.objects.set_config),
            "enable_http_proxy",
            False,
        )
        yield deferToDatabase(
            transactional(Config.objects.set_config),
            "http_proxy",
            factory.make_url(),
        )
        self.patch(config, "is_config_present").return_value = True
        expected_state = yield maybeDeferred(service.getExpectedState)
        self.assertEqual(
            (SERVICE_STATE.OFF, "proxy disabled."), expected_state
        )

    @wait_for_reactor
    @inlineCallbacks
    def test_getExpectedState_returns_on_for_proxy_on_but_unset(self):
        service = self.make_proxy_service()
        yield deferToDatabase(
            transactional(Config.objects.set_config), "enable_http_proxy", True
        )
        yield deferToDatabase(
            transactional(Config.objects.set_config), "http_proxy", ""
        )
        self.patch(config, "is_config_present").return_value = True
        expected_state = yield maybeDeferred(service.getExpectedState)
        self.assertEqual((SERVICE_STATE.ON, None), expected_state)

    @wait_for_reactor
    @inlineCallbacks
    def test_getExpectedState_returns_off_for_proxy_on_and_set(self):
        service = self.make_proxy_service()
        yield deferToDatabase(
            transactional(Config.objects.set_config), "enable_http_proxy", True
        )
        yield deferToDatabase(
            transactional(Config.objects.set_config),
            "http_proxy",
            factory.make_url(),
        )
        self.patch(config, "is_config_present").return_value = True
        expected_state = yield maybeDeferred(service.getExpectedState)
        self.assertEqual(
            (
                SERVICE_STATE.OFF,
                "disabled, alternate proxy is configured in settings.",
            ),
            expected_state,
        )

    @wait_for_reactor
    @inlineCallbacks
    def test_getExpectedState_returns_on_for_proxy_on_and_set_peer_proxy(self):
        service = self.make_proxy_service()
        yield deferToDatabase(
            transactional(Config.objects.set_config), "enable_http_proxy", True
        )
        yield deferToDatabase(
            transactional(Config.objects.set_config), "use_peer_proxy", True
        )
        yield deferToDatabase(
            transactional(Config.objects.set_config),
            "http_proxy",
            factory.make_url(),
        )
        self.patch(config, "is_config_present").return_value = True
        expected_state = yield maybeDeferred(service.getExpectedState)
        self.assertEqual((SERVICE_STATE.ON, None), expected_state)
