# Copyright 2018 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

import os
from pathlib import Path

from maasserver.regiondservices import http
from maastesting.testcase import MAASTestCase
from maastesting.twisted import always_succeed_with


class TestRegionHTTPService(MAASTestCase):
    """Tests for `RegionHTTPService`."""

    def setUp(self):
        super().setUp()

    def make_startable_RegionHTTPService(self):
        return http.RegionHTTPService()

    def test_configure_and_reload_not_snap(self):
        mock_reloadService = self.patch(http.service_monitor, "reloadService")
        mock_reloadService.return_value = always_succeed_with(None)

        mock_configure = self.patch(http.RegionHTTPService, "_configure")

        service = self.make_startable_RegionHTTPService()
        service.startService()

        mock_reloadService.assert_called_once_with("reverse_proxy")
        mock_configure.assert_called_once()

    def test_configure_and_reload_in_snap(self):
        self.patch(os, "environ", {"SNAP": "true"})
        mock_restartService = self.patch(
            http.service_monitor, "restartService"
        )
        mock_restartService.return_value = always_succeed_with(None)

        mock_configure = self.patch(http.RegionHTTPService, "_configure")

        service = self.make_startable_RegionHTTPService()
        service.startService()

        mock_restartService.assert_called_once_with("reverse_proxy")
        mock_configure.assert_called_once()

    def test_configure_not_snap(self):
        tempdir = self.make_dir()
        nginx_conf = Path(tempdir) / "regiond.nginx.conf"
        service = self.make_startable_RegionHTTPService()
        self.patch(http, "compose_http_config_path").return_value = str(
            nginx_conf
        )
        service._configure()
        # MAASDataFixture updates `MAAS_DATA` in the environment to point to this new location.
        data_path = os.getenv("MAAS_DATA")
        self.assertIn(
            f"{data_path}/maas-regiond-webapp.sock;", nginx_conf.read_text()
        )

    def test_configure_in_snap(self):
        self.patch(
            os,
            "environ",
            {"MAAS_HTTP_SOCKET_PATH": "/snap/maas/maas-regiond-webapp.sock"},
        )
        tempdir = self.make_dir()
        nginx_conf = Path(tempdir) / "regiond.nginx.conf"
        service = self.make_startable_RegionHTTPService()
        self.patch(http, "compose_http_config_path").return_value = str(
            nginx_conf
        )
        service._configure()
        self.assertIn(
            "server unix:/snap/maas/maas-regiond-webapp.sock;",
            nginx_conf.read_text(),
        )
