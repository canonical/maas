# Copyright 2015-2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

import http.client
import random

from django.conf import settings
from django.urls import reverse
from testtools.content import text_content

from maasserver.models import PackageRepository
from maasserver.models.config import Config
from maasserver.testing.api import APITestCase
from maasserver.testing.factory import factory
from maasserver.testing.osystems import (
    make_osystem_with_releases,
    make_usable_osystem,
)

# Names forbidden for use via the Web API.
FORBIDDEN_NAMES = {
    "active_discovery_last_scan",
    "commissioning_osystem",
    "maas_url",
    "omapi_key",
    "rpc_shared_secret",
    "tls_port",
    "uuid",
    "vault_enabled",
}


class TestMAASHandlerAPI(APITestCase.ForUser):
    def test_get_config_default_distro_series(self):
        default_distro_series = factory.make_name("distro_series")
        Config.objects.set_config(
            "default_distro_series", default_distro_series
        )
        response = self.client.get(
            reverse("maas_handler"),
            {"op": "get_config", "name": "default_distro_series"},
        )
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        expected = '"%s"' % default_distro_series
        self.assertEqual(
            expected.encode(settings.DEFAULT_CHARSET), response.content
        )

    def test_set_config_default_distro_series(self):
        self.become_admin()
        osystem, releases = make_usable_osystem(self)
        Config.objects.set_config("default_osystem", osystem)
        selected_release = releases[0]
        response = self.client.post(
            reverse("maas_handler"),
            {
                "op": "set_config",
                "name": "default_distro_series",
                "value": selected_release,
            },
        )
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        self.assertEqual(
            selected_release,
            Config.objects.get_config("default_distro_series"),
        )

    def test_set_config_only_default_osystem_are_valid_for_distro_series(self):
        self.become_admin()
        default_osystem, _ = make_osystem_with_releases(self)
        _, other_osystem_releases = make_osystem_with_releases(self)
        factory.make_default_ubuntu_release_bootable()
        Config.objects.set_config("default_osystem", default_osystem)
        invalid_release = other_osystem_releases[0]
        response = self.client.post(
            reverse("maas_handler"),
            {
                "op": "set_config",
                "name": "default_distro_series",
                "value": invalid_release,
            },
        )
        self.assertEqual(
            http.client.BAD_REQUEST, response.status_code, response.content
        )

    def assertInvalidConfigurationSetting(self, name, response):
        self.addDetail(
            "Response for op={get,set}_config&name=%s" % name,
            text_content(
                response.serialize().decode(settings.DEFAULT_CHARSET)
            ),
        )
        self.assertEqual(response.status_code, http.client.BAD_REQUEST)
        self.assertEqual(response["Content-Type"], "application/json")
        self.assertIn(
            f"{name} is not a valid config setting (valid settings are: ",
            response.json().get(name, [""])[0],
        )

    def test_get_config_forbidden_config_items(self):
        for name in FORBIDDEN_NAMES:
            response = self.client.get(
                reverse("maas_handler"), {"op": "get_config", "name": name}
            )
            self.assertInvalidConfigurationSetting(name, response)

    def test_set_config_forbidden_config_items(self):
        self.become_admin()
        for name in FORBIDDEN_NAMES:
            response = self.client.post(
                reverse("maas_handler"),
                {
                    "op": "set_config",
                    "name": name,
                    "value": factory.make_name("nonsense"),
                },
            )
            self.assertInvalidConfigurationSetting(name, response)

    def test_get_config_ntp_server_alias_for_ntp_servers(self):
        ntp_servers = factory.make_hostname() + " " + factory.make_hostname()
        Config.objects.set_config("ntp_servers", ntp_servers)
        response = self.client.get(
            reverse("maas_handler"), {"op": "get_config", "name": "ntp_server"}
        )
        self.assertEqual(response.status_code, http.client.OK)
        self.assertEqual(response["Content-Type"], "application/json")
        self.assertEqual(response.json(), ntp_servers)

    def test_set_config_ntp_server_alias_for_ntp_servers(self):
        self.become_admin()
        ntp_servers = factory.make_hostname() + " " + factory.make_hostname()
        response = self.client.post(
            reverse("maas_handler"),
            {"op": "set_config", "name": "ntp_server", "value": ntp_servers},
        )
        self.assertEqual(response.status_code, http.client.OK)
        self.assertEqual(ntp_servers, Config.objects.get_config("ntp_servers"))

    def test_get_main_archive_overrides_to_package_repository(self):
        PackageRepository.objects.all().delete()
        main_url = factory.make_url(scheme="http")
        factory.make_PackageRepository(
            url=main_url, default=True, arches=["i386", "amd64"]
        )
        response = self.client.get(
            reverse("maas_handler"),
            {"op": "get_config", "name": "main_archive"},
        )
        self.assertEqual(response.status_code, http.client.OK)
        self.assertEqual(response["Content-Type"], "application/json")
        self.assertEqual(response.json(), main_url)

    def test_get_ports_archive_overrides_to_package_repository(self):
        PackageRepository.objects.all().delete()
        ports_url = factory.make_url(scheme="http")
        factory.make_PackageRepository(
            url=ports_url, default=True, arches=["arm64", "armhf", "powerpc"]
        )
        response = self.client.get(
            reverse("maas_handler"),
            {"op": "get_config", "name": "ports_archive"},
        )
        self.assertEqual(response.status_code, http.client.OK)
        self.assertEqual(response["Content-Type"], "application/json")
        self.assertEqual(response.json(), ports_url)

    def test_set_main_archive_overrides_to_package_repository(self):
        self.become_admin()
        main_archive = factory.make_url(scheme="http")
        response = self.client.post(
            reverse("maas_handler"),
            {
                "op": "set_config",
                "name": "main_archive",
                "value": main_archive,
            },
        )
        self.assertEqual(response.status_code, http.client.OK)
        self.assertEqual(
            main_archive, PackageRepository.get_main_archive().url
        )

    def test_set_ports_archive_overrides_to_package_repository(self):
        self.become_admin()
        ports_archive = factory.make_url(scheme="http")
        response = self.client.post(
            reverse("maas_handler"),
            {
                "op": "set_config",
                "name": "ports_archive",
                "value": ports_archive,
            },
        )
        self.assertEqual(response.status_code, http.client.OK)
        self.assertEqual(
            ports_archive, PackageRepository.get_ports_archive().url
        )

    def test_set_config_use_peer_proxy(self):
        self.become_admin()
        response = self.client.post(
            reverse("maas_handler"),
            {"op": "set_config", "name": "use_peer_proxy", "value": True},
        )
        self.assertEqual(http.client.OK, response.status_code)
        self.assertTrue(Config.objects.get_config("use_peer_proxy"))

    def test_set_config_prefer_v4_proxy(self):
        self.become_admin()
        response = self.client.post(
            reverse("maas_handler"),
            {"op": "set_config", "name": "prefer_v4_proxy", "value": True},
        )
        self.assertEqual(http.client.OK, response.status_code)
        self.assertTrue(Config.objects.get_config("prefer_v4_proxy"))

    def test_set_config_boot_images_no_proxy(self):
        self.become_admin()
        response = self.client.post(
            reverse("maas_handler"),
            {
                "op": "set_config",
                "name": "boot_images_no_proxy",
                "value": True,
            },
        )
        self.assertEqual(http.client.OK, response.status_code)
        self.assertTrue(Config.objects.get_config("boot_images_no_proxy"))

    def test_get_config_maas_internal_domain(self):
        internal_domain = factory.make_name("internal")
        Config.objects.set_config("maas_internal_domain", internal_domain)
        response = self.client.get(
            reverse("maas_handler"),
            {"op": "get_config", "name": "maas_internal_domain"},
        )
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        expected = '"%s"' % internal_domain
        self.assertEqual(
            expected.encode(settings.DEFAULT_CHARSET), response.content
        )

    def test_set_config_maas_internal_domain(self):
        self.become_admin()
        internal_domain = factory.make_name("internal")
        response = self.client.post(
            reverse("maas_handler"),
            {
                "op": "set_config",
                "name": "maas_internal_domain",
                "value": internal_domain,
            },
        )
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        self.assertEqual(
            internal_domain, Config.objects.get_config("maas_internal_domain")
        )

    def test_get_config_maas_ipmi_user(self):
        ipmi_user = factory.make_name("internal")
        Config.objects.set_config("maas_auto_ipmi_user", ipmi_user)
        response = self.client.get(
            reverse("maas_handler"),
            {"op": "get_config", "name": "maas_auto_ipmi_user"},
        )
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        expected = '"%s"' % ipmi_user
        self.assertEqual(
            expected.encode(settings.DEFAULT_CHARSET), response.content
        )

    def test_set_config_maas_ipmi_user(self):
        self.become_admin()
        ipmi_user = factory.make_name("internal")
        response = self.client.post(
            reverse("maas_handler"),
            {
                "op": "set_config",
                "name": "maas_auto_ipmi_user",
                "value": ipmi_user,
            },
        )
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        self.assertEqual(
            ipmi_user, Config.objects.get_config("maas_auto_ipmi_user")
        )


class TestMAASHandlerAPIForProxyPort(APITestCase.ForUser):
    scenarios = [
        ("valid-port", {"port": random.randint(5300, 65535), "valid": True}),
        (
            "invalid-port_maas-reserved-range",
            {"port": random.randint(5240, 5270), "valid": False},
        ),
        (
            "invalid-port_system-services",
            {"port": random.randint(0, 1023), "valid": False},
        ),
        (
            "invalid-port_out-of-range",
            {"port": random.randint(65536, 70000), "valid": False},
        ),
    ]

    def test_set_config_maas_proxy_port(self):
        self.become_admin()
        port = self.port
        response = self.client.post(
            reverse("maas_handler"),
            {"op": "set_config", "name": "maas_proxy_port", "value": port},
        )
        if self.valid:
            self.assertEqual(http.client.OK, response.status_code)
            self.assertEqual(
                port, Config.objects.get_config("maas_proxy_port")
            )
        else:
            self.assertEqual(
                http.client.BAD_REQUEST, response.status_code, response.content
            )
