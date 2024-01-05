# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `maasserver.utils.keys`."""


import http

from hypothesis import given, settings
from hypothesis.strategies import sampled_from
import requests as requests_module

from maasserver.enum import KEYS_PROTOCOL_TYPE
from maasserver.models import Config
from maasserver.models.signals.bootsources import (
    signals as bootsources_signals,
)
from maasserver.testing import get_data
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
import maasserver.utils.keys as keys_module
from maasserver.utils.keys import (
    get_github_ssh_keys,
    get_launchpad_ssh_keys,
    get_protocol_keys,
    get_proxies,
    ImportSSHKeysError,
)


class TestKeys(MAASServerTestCase):
    def setUp(self):
        super().setUp()
        # Disable boot source cache signals.
        self.addCleanup(bootsources_signals.enable)
        bootsources_signals.disable()

    def test_get_proxies_returns_proxies(self):
        proxy_address = factory.make_name("proxy")
        Config.objects.set_config("http_proxy", proxy_address)
        proxies = get_proxies()
        self.assertEqual(
            (proxy_address, proxy_address), (proxies["http"], proxies["https"])
        )

    def test_get_proxies_returns_None_for_no_proxies(self):
        proxies = get_proxies()
        self.assertIsNone(proxies)

    @settings(deadline=None)
    @given(sampled_from([KEYS_PROTOCOL_TYPE.LP, KEYS_PROTOCOL_TYPE.GH]))
    def test_get_protocol_keys_attempts_retrival(self, protocol):
        auth_id = factory.make_name("auth_id")
        if protocol == KEYS_PROTOCOL_TYPE.LP:
            mock_get_keys = self.patch(keys_module, "get_launchpad_ssh_keys")
        else:
            mock_get_keys = self.patch(keys_module, "get_github_ssh_keys")
        get_protocol_keys(protocol, auth_id)
        mock_get_keys.assert_called_once_with(auth_id)

    @settings(deadline=None)
    @given(sampled_from([KEYS_PROTOCOL_TYPE.LP, KEYS_PROTOCOL_TYPE.GH]))
    def test_get_protocol_keys_crashes_on_no_keys(self, protocol):
        auth_id = factory.make_name("auth_id")
        if protocol == KEYS_PROTOCOL_TYPE.LP:
            mock_get_keys = self.patch(keys_module, "get_launchpad_ssh_keys")
        else:
            mock_get_keys = self.patch(keys_module, "get_github_ssh_keys")
        mock_get_keys.return_value = []
        self.assertRaises(
            ImportSSHKeysError, get_protocol_keys, protocol, auth_id
        )

    def test_get_launchpad_ssh_keys_returns_keys(self):
        auth_id = factory.make_name("auth_id")
        key_string = get_data("data/test_rsa0.pub") + get_data(
            "data/test_rsa1.pub"
        )
        mock_requests = self.patch(requests_module, "get")
        mock_requests.return_value.text = key_string
        keys = get_launchpad_ssh_keys(auth_id)
        url = "https://launchpad.net/~%s/+sshkeys" % auth_id
        mock_requests.assert_called_once_with(url, proxies=None)
        self.assertEqual(keys, [key for key in key_string.splitlines() if key])

    @settings(deadline=None)
    @given(sampled_from([http.HTTPStatus.NOT_FOUND, http.HTTPStatus.GONE]))
    def test_get_launchpad_crashes_for_user_not_found(self, error):
        auth_id = factory.make_name("auth_id")
        mock_requests = self.patch(requests_module, "get")
        mock_requests.return_value.status_code = error
        self.assertRaises(ImportSSHKeysError, get_launchpad_ssh_keys, auth_id)

    def test_get_protocol_keys_returns_github_keys(self):
        auth_id = factory.make_name("auth_id")
        key_string = str([dict(key=get_data("data/test_rsa0.pub"))])
        mock_requests = self.patch(requests_module, "get")
        mock_requests.return_value.text = key_string
        keys = get_github_ssh_keys(auth_id)
        url = "https://api.github.com/users/%s/keys" % auth_id
        mock_requests.assert_called_once_with(url, proxies=None)
        self.assertEqual(
            keys, [data["key"] for data in key_string if "key" in data]
        )

    @settings(deadline=None)
    @given(sampled_from([http.HTTPStatus.NOT_FOUND, http.HTTPStatus.GONE]))
    def test_get_github_crashes_for_user_not_found(self, error):
        auth_id = factory.make_name("auth_id")
        mock_requests = self.patch(requests_module, "get")
        mock_requests.return_value.status_code = error
        self.assertRaises(ImportSSHKeysError, get_github_ssh_keys, auth_id)
