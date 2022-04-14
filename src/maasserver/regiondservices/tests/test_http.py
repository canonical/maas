# Copyright 2018 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

import os
from pathlib import Path
from unittest.mock import call, Mock

from django.db import transaction
from twisted.internet.defer import inlineCallbacks

from maasserver.models.config import Config
from maasserver.regiondservices import http
from maasserver.testing.testcase import MAASTransactionServerTestCase
from maasserver.triggers.system import register_system_triggers
from maasserver.triggers.testing import TransactionalHelpersMixin
from maasserver.utils.threads import deferToDatabase
from maastesting.crochet import wait_for
from provisioningserver.utils.twisted import DeferredValue

wait_for_reactor = wait_for()


class TestRegionHTTPService(
    TransactionalHelpersMixin, MAASTransactionServerTestCase
):
    """Tests for `RegionHTTPService`."""

    def set_config(self):
        with transaction.atomic():
            Config.objects.set_config("tls_key", "maas-key")
            Config.objects.set_config("tls_cert", "maas-cert")
            Config.objects.set_config("tls_port", 5443)

    def get_config(self):
        return Config.objects.get_configs(["tls_key", "tls_cert", "tls_port"])

    @wait_for_reactor
    @inlineCallbacks
    def test_configure_and_reload_not_snap(self):
        service = http.RegionHTTPService()
        mock_reloadService = self.patch(http.service_monitor, "reloadService")
        mock_configure = self.patch(service, "_configure")

        m = Mock()
        m.attach_mock(mock_reloadService, "mock_reloadService")
        m.attach_mock(mock_configure, "mock_configure")

        yield deferToDatabase(self.set_config)
        yield service.startService()

        expected_calls = [
            call.mock_configure(
                http._Configuration(
                    key="maas-key", cert="maas-cert", port=5443
                )
            ),
            call.mock_reloadService("reverse_proxy"),
        ]

        assert m.mock_calls == expected_calls

    @wait_for_reactor
    @inlineCallbacks
    def test_configure_and_reload_in_snap(self):
        self.patch(os, "environ", {"SNAP": "true"})

        service = http.RegionHTTPService()
        mock_restartService = self.patch(
            http.service_monitor, "restartService"
        )
        mock_configure = self.patch(service, "_configure")

        m = Mock()
        m.attach_mock(mock_restartService, "mock_restartService")
        m.attach_mock(mock_configure, "mock_configure")

        yield deferToDatabase(self.set_config)
        yield service.startService()

        expected_calls = [
            call.mock_configure(
                http._Configuration(
                    key="maas-key", cert="maas-cert", port=5443
                )
            ),
            call.mock_restartService("reverse_proxy"),
        ]

        assert m.mock_calls == expected_calls

    def test_configure_not_snap(self):
        tempdir = self.make_dir()
        nginx_conf = Path(tempdir) / "regiond.nginx.conf"
        service = http.RegionHTTPService()
        self.patch(http, "compose_http_config_path").return_value = str(
            nginx_conf
        )

        mock_create_cert_files = self.patch(service, "_create_cert_files")
        mock_create_cert_files.return_value = ("key_path", "cert_path")

        service._configure(http._Configuration("maas-key", "maas-cert", 5443))

        # MAASDataFixture updates `MAAS_DATA` in the environment to point to this new location.
        data_path = os.getenv("MAAS_DATA")
        nginx_config = nginx_conf.read_text()
        self.assertIn(f"{data_path}/maas-regiond-webapp.sock;", nginx_config)
        self.assertIn("root /usr/share/maas/web/static;", nginx_config)
        self.assertIn("listen 5443 ssl http2;", nginx_config)
        self.assertIn("ssl_certificate cert_path;", nginx_config)
        self.assertIn("ssl_certificate_key key_path;", nginx_config)

    def test_configure_in_snap(self):
        self.patch(
            os,
            "environ",
            {
                "MAAS_HTTP_SOCKET_PATH": "/snap/maas/maas-regiond-webapp.sock",
                "SNAP": "/snap/maas/5443",
                "MAAS_HTTP_CONFIG_DIR": os.getenv("MAAS_DATA"),
            },
        )
        tempdir = self.make_dir()
        nginx_conf = Path(tempdir) / "regiond.nginx.conf"
        service = http.RegionHTTPService()
        self.patch(http, "compose_http_config_path").return_value = str(
            nginx_conf
        )

        mock_create_cert_files = self.patch(service, "_create_cert_files")
        mock_create_cert_files.return_value = ("key_path", "cert_path")

        service._configure(http._Configuration("maas-key", "maas-cert", 5443))

        nginx_config = nginx_conf.read_text()
        self.assertIn(
            "server unix:/snap/maas/maas-regiond-webapp.sock;", nginx_config
        )
        self.assertIn(
            "root /snap/maas/5443/usr/share/maas/web/static;", nginx_config
        )
        self.assertIn("listen 5443 ssl http2;", nginx_config)
        self.assertIn("ssl_certificate cert_path;", nginx_config)
        self.assertIn("ssl_certificate_key key_path;", nginx_config)

    def test_configure_https_also_has_http_server(self):
        tempdir = self.make_dir()
        nginx_conf = Path(tempdir) / "regiond.nginx.conf"
        service = http.RegionHTTPService()
        self.patch(http, "compose_http_config_path").return_value = str(
            nginx_conf
        )

        mock_create_cert_files = self.patch(service, "_create_cert_files")
        mock_create_cert_files.return_value = ("key_path", "cert_path")

        service._configure(http._Configuration("maas-key", "maas-cert", 5443))

        nginx_config = nginx_conf.read_text()
        self.assertIn("listen 5443 ssl http2;", nginx_config)
        self.assertIn("listen 5240;", nginx_config)
        self.assertIn("location /MAAS/api/2.0/machines {", nginx_config)

    @wait_for_reactor
    @inlineCallbacks
    def test_registers_and_unregisters_listener(self):
        listener = Mock()
        service = http.RegionHTTPService(postgresListener=listener)
        self.patch(http.service_monitor, "reloadService")
        self.patch(service, "_configure")

        yield service.startService()
        listener.register.assert_called_once_with(
            "sys_reverse_proxy", service._consume_event
        )

        service.stopService()
        listener.unregister.assert_called_once_with(
            "sys_reverse_proxy", service._consume_event
        )

    @wait_for_reactor
    @inlineCallbacks
    def test_handler_is_called_on_config_change(self):
        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register("sys_reverse_proxy", lambda *args: dv.set(args))
        yield listener.startService()
        yield deferToDatabase(register_system_triggers)
        yield deferToDatabase(self.set_config)
        try:
            yield dv.get(timeout=2)
            self.assertEqual(("sys_reverse_proxy", ""), dv.value)
        finally:
            yield listener.stopService()

    @wait_for_reactor
    @inlineCallbacks
    def test_data_is_consistent_when_notified(self):
        listener = self.make_listener_without_delay()
        dv = DeferredValue()
        listener.register("sys_reverse_proxy", lambda *args: dv.set(args))
        yield listener.startService()
        yield deferToDatabase(register_system_triggers)
        yield deferToDatabase(self.set_config)
        try:
            yield dv.get(timeout=2)
            self.assertEqual(("sys_reverse_proxy", ""), dv.value)
        finally:
            yield listener.stopService()

        config = yield deferToDatabase(self.get_config)

        self.assertEqual(
            {"tls_key": "maas-key", "tls_cert": "maas-cert", "tls_port": 5443},
            config,
        )
