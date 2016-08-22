# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `maasserver.utils.keys`."""

__all__ = []


from maasserver.enum import KEYS_PROTOCOL_TYPE
from maasserver.testing import get_data
from maasserver.testing.factory import factory
from maasserver.utils.keys import get_protocol_keys
from maastesting.matchers import MockCalledOnceWith
from maastesting.testcase import MAASTestCase
import requests as requests_module
from testtools.matchers import Equals


class TestKeys(MAASTestCase):

    def test__returns_launchpad_keys(self):
        protocol = KEYS_PROTOCOL_TYPE.LP
        auth_id = factory.make_name('auth_id')
        key_string = get_data('data/test_rsa0.pub') \
            + get_data('data/test_rsa1.pub')
        mock_requests = self.patch(requests_module, 'get')
        mock_requests.return_value.text = key_string
        keys = get_protocol_keys(protocol, auth_id)
        url = 'https://launchpad.net/~%s/+sshkeys' % auth_id
        self.expectThat(mock_requests, MockCalledOnceWith(url))
        self.expectThat(keys, Equals(key_string.split('\n')))

    def test__returns_git_keys(self):
        protocol = KEYS_PROTOCOL_TYPE.GH
        auth_id = factory.make_name('auth_id')
        key_string = get_data('data/test_rsa0.pub') \
            + get_data('data/test_rsa1.pub')
        mock_requests = self.patch(requests_module, 'get')
        mock_requests.return_value.text = key_string
        keys = get_protocol_keys(protocol, auth_id)
        url = 'https://api.github.com/users/%s/keys' % auth_id
        self.expectThat(mock_requests, MockCalledOnceWith(url))
        self.expectThat(keys, Equals(key_string.split('\n')))
