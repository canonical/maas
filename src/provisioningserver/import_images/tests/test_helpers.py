# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for the `helpers` module."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

from maastesting.factory import factory
from maastesting.matchers import MockCalledOnceWith
from maastesting.testcase import MAASTestCase
import mock
from provisioningserver.import_images import helpers
from simplestreams.util import SignatureMissingException


class TestGetSigningPolicy(MAASTestCase):
    """Tests for `get_signing_policy`."""

    def test_picks_nonchecking_policy_for_json_index(self):
        path = 'streams/v1/index.json'
        policy = helpers.get_signing_policy(path)
        content = factory.getRandomString()
        self.assertEqual(
            content,
            policy(content, path, factory.make_name('keyring')))

    def test_picks_checking_policy_for_sjson_index(self):
        path = 'streams/v1/index.sjson'
        content = factory.getRandomString()
        policy = helpers.get_signing_policy(path)
        self.assertRaises(
            SignatureMissingException,
            policy, content, path, factory.make_name('keyring'))

    def test_picks_checking_policy_for_json_gpg_index(self):
        path = 'streams/v1/index.json.gpg'
        content = factory.getRandomString()
        policy = helpers.get_signing_policy(path)
        self.assertRaises(
            SignatureMissingException,
            policy, content, path, factory.make_name('keyring'))

    def test_injects_default_keyring_if_passed(self):
        path = 'streams/v1/index.json.gpg'
        content = factory.getRandomString()
        keyring = factory.make_name('keyring')
        self.patch(helpers, 'policy_read_signed')
        policy = helpers.get_signing_policy(path, keyring)
        policy(content, path)
        self.assertThat(
            helpers.policy_read_signed,
            MockCalledOnceWith(mock.ANY, mock.ANY, keyring=keyring))
