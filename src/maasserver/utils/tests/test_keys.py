# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `maasserver.utils.keys`."""

__all__ = []

import http

from hypothesis import given
from hypothesis.strategies import sampled_from
from maasserver.enum import KEYS_PROTOCOL_TYPE
from maasserver.testing import get_data
from maasserver.testing.factory import factory
from maasserver.utils.keys import (
    get_github_ssh_keys,
    get_launchpad_ssh_keys,
    get_protocol_keys,
    ImportSSHKeysError,
)
import maasserver.utils.keys as keys_module
from maastesting.matchers import MockCalledOnceWith
from maastesting.testcase import MAASTestCase
import requests as requests_module
from testtools.matchers import Equals


class TestKeys(MAASTestCase):

    @given(sampled_from([KEYS_PROTOCOL_TYPE.LP, KEYS_PROTOCOL_TYPE.GH]))
    def test_get_protocol_keys_attempts_retrival(self, protocol):
        auth_id = factory.make_name('auth_id')
        if protocol == KEYS_PROTOCOL_TYPE.LP:
            mock_get_keys = self.patch(keys_module, 'get_launchpad_ssh_keys')
        else:
            mock_get_keys = self.patch(keys_module, 'get_github_ssh_keys')
        get_protocol_keys(protocol, auth_id)
        self.assertThat(mock_get_keys, MockCalledOnceWith(auth_id))

    @given(sampled_from([KEYS_PROTOCOL_TYPE.LP, KEYS_PROTOCOL_TYPE.GH]))
    def test_get_protocol_keys_crashes_on_no_keys(self, protocol):
        auth_id = factory.make_name('auth_id')
        if protocol == KEYS_PROTOCOL_TYPE.LP:
            mock_get_keys = self.patch(keys_module, 'get_launchpad_ssh_keys')
        else:
            mock_get_keys = self.patch(keys_module, 'get_github_ssh_keys')
        mock_get_keys.return_value = []
        self.assertRaises(
            ImportSSHKeysError, get_protocol_keys, protocol, auth_id)

    def test_get_launchpad_ssh_keys_returns_keys(self):
        auth_id = factory.make_name('auth_id')
        key_string = get_data('data/test_rsa0.pub') \
            + get_data('data/test_rsa1.pub')
        mock_requests = self.patch(requests_module, 'get')
        mock_requests.return_value.text = key_string
        keys = get_launchpad_ssh_keys(auth_id)
        url = 'https://launchpad.net/~%s/+sshkeys' % auth_id
        self.expectThat(mock_requests, MockCalledOnceWith(url))
        self.expectThat(
            keys, Equals(
                [key for key in key_string.splitlines() if key]))

    def test_get_launchpad_crashes_for_user_not_found(self):
        auth_id = factory.make_name('auth_id')
        mock_requests = self.patch(requests_module, 'get')
        mock_requests.return_value.status_code = http.HTTPStatus.NOT_FOUND
        self.assertRaises(ImportSSHKeysError, get_launchpad_ssh_keys, auth_id)

    def test_get_protocol_keys_returns_github_keys(self):
        auth_id = factory.make_name('auth_id')
        key_string = str(
            [dict(key=get_data('data/test_rsa0.pub'))])
        mock_requests = self.patch(requests_module, 'get')
        mock_requests.return_value.text = key_string
        keys = get_github_ssh_keys(auth_id)
        url = 'https://api.github.com/users/%s/keys' % auth_id
        self.expectThat(mock_requests, MockCalledOnceWith(url))
        self.expectThat(
            keys, Equals(
                [data['key'] for data in key_string if 'key' in data]))

    def test_get_github_crashes_for_user_not_found(self):
        auth_id = factory.make_name('auth_id')
        mock_requests = self.patch(requests_module, 'get')
        mock_requests.return_value.status_code = http.HTTPStatus.NOT_FOUND
        self.assertRaises(ImportSSHKeysError, get_github_ssh_keys, auth_id)
