# Copyright 2014-2018 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for the WindowsOS module."""

import random

import pytest

from maascommon.osystem import Node, Token
from maascommon.osystem.windows import (
    BOOT_IMAGE_PURPOSE,
    REQUIRE_LICENSE_KEY,
    WINDOWS_CHOICES,
    WINDOWS_DEFAULT,
    WindowsOS,
)
from maastesting.factory import factory


class TestWindowsOS:
    def test_get_boot_image_purposes_xinstall(self):
        osystem = WindowsOS()
        assert [
            BOOT_IMAGE_PURPOSE.XINSTALL
        ] == osystem.get_boot_image_purposes()

    def test_get_default_release(self):
        osystem = WindowsOS()
        expected = osystem.get_default_release()
        assert expected == WINDOWS_DEFAULT

    def test_get_release_title(self):
        osystem = WindowsOS()
        release = random.choice(list(WINDOWS_CHOICES))
        assert WINDOWS_CHOICES[release] == osystem.get_release_title(release)

    def test_requires_license_key_True(self):
        osystem = WindowsOS()
        for release in REQUIRE_LICENSE_KEY:
            assert osystem.requires_license_key(release) is True

    def test_requires_license_key_False(self):
        osystem = WindowsOS()
        not_required = set(WINDOWS_CHOICES.keys()).difference(
            REQUIRE_LICENSE_KEY
        )
        for release in not_required:
            assert osystem.requires_license_key(release) is False

    def test_validate_license_key(self):
        osystem = WindowsOS()
        parts = [factory.make_string(size=5) for _ in range(5)]
        key = "-".join(parts)
        assert (
            osystem.validate_license_key(REQUIRE_LICENSE_KEY[0], key) is True
        )

    def test_validate_license_key_invalid(self):
        osystem = WindowsOS()
        keys = [factory.make_string() for _ in range(3)]
        for key in keys:
            assert (
                osystem.validate_license_key(REQUIRE_LICENSE_KEY[0], key)
                is False
            )

    def make_node(self, hostname=None):
        if hostname is None:
            machine = factory.make_name("hostname")
            dns = factory.make_name("dns")
            hostname = f"{machine}.{dns}"
        return Node(
            system_id=factory.make_name("system_id"), hostname=hostname
        )

    def make_token(self, consumer_key=None, token_key=None, token_secret=None):
        if consumer_key is None:
            consumer_key = factory.make_name("consumer_key")
        if token_key is None:
            token_key = factory.make_name("token_key")
        if token_secret is None:
            token_secret = factory.make_name("secret_key")
        return Token(
            consumer_key=consumer_key,
            token_key=token_key,
            token_secret=token_secret,
        )

    def test_compose_pressed_not_implemented_for_curtin(self):
        osystem = WindowsOS()
        node = self.make_node()
        token = self.make_token()
        url = factory.make_name("url")
        with pytest.raises(NotImplementedError):
            osystem.compose_preseed(
                "curtin",
                node,
                token,
                url,
            )

    def test_compose_preseed_has_required_keys(self):
        osystem = WindowsOS()
        node = self.make_node()
        token = self.make_token()
        url = factory.make_name("url")
        required_keys = {
            "maas_metadata_url",
            "maas_oauth_consumer_secret",
            "maas_oauth_consumer_key",
            "maas_oauth_token_key",
            "maas_oauth_token_secret",
            "hostname",
        }
        preseed = osystem.compose_preseed("default", node, token, url)
        assert required_keys == preseed.keys()

    def test_compose_preseed_uses_only_hostname(self):
        osystem = WindowsOS()
        machine = factory.make_name("hostname")
        dns = factory.make_name("dns")
        hostname = f"{machine}.{dns}"
        node = self.make_node(hostname=hostname)
        token = self.make_token()
        url = factory.make_name("url")
        preseed = osystem.compose_preseed("default", node, token, url)
        assert machine == preseed["hostname"]

    def test_compose_preseed_truncates_hostname(self):
        osystem = WindowsOS()
        machine = factory.make_name("hostname", size=20)
        dns = factory.make_name("dns")
        hostname = f"{machine}.{dns}"
        node = self.make_node(hostname=hostname)
        token = self.make_token()
        url = factory.make_name("url")
        preseed = osystem.compose_preseed("default", node, token, url)
        assert 15 == len(preseed["hostname"])

    def test_compose_preseed_includes_oauth(self):
        osystem = WindowsOS()
        node = self.make_node()
        consumer_key = factory.make_name("consumer_key")
        token_key = factory.make_name("token_key")
        token_secret = factory.make_name("secret_key")
        token = self.make_token(
            consumer_key=consumer_key,
            token_key=token_key,
            token_secret=token_secret,
        )
        url = factory.make_name("url")
        preseed = osystem.compose_preseed("default", node, token, url)
        assert "" == preseed["maas_oauth_consumer_secret"]
        assert consumer_key == preseed["maas_oauth_consumer_key"]
        assert token_key == preseed["maas_oauth_token_key"]
        assert token_secret == preseed["maas_oauth_token_secret"]

    def test_compose_preseed_includes_metadata_url(self):
        osystem = WindowsOS()
        node = self.make_node()
        token = self.make_token()
        url = factory.make_name("url")
        preseed = osystem.compose_preseed("default", node, token, url)
        assert url == preseed["maas_metadata_url"]
