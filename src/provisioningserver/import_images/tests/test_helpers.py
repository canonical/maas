# Copyright 2014-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for the `helpers` module."""


from simplestreams.util import SignatureMissingException

from maastesting.factory import factory
from maastesting.testcase import MAASTestCase
from provisioningserver.import_images import helpers


class TestGetSigningPolicy(MAASTestCase):
    """Tests for `get_signing_policy`."""

    def test_picks_nonchecking_policy_for_json_index(self):
        path = "streams/v1/index.json"
        policy = helpers.get_signing_policy(path)
        content = factory.make_string()
        self.assertEqual(
            content, policy(content, path, factory.make_name("keyring"))
        )

    def test_picks_checking_policy_for_sjson_index(self):
        path = "streams/v1/index.sjson"
        content = factory.make_string()
        policy = helpers.get_signing_policy(path)
        self.assertRaises(
            SignatureMissingException,
            policy,
            content,
            path,
            factory.make_name("keyring"),
        )

    def test_picks_checking_policy_for_json_gpg_index(self):
        path = "streams/v1/index.json.gpg"
        content = factory.make_string()
        policy = helpers.get_signing_policy(path)
        self.assertRaises(
            SignatureMissingException,
            policy,
            content,
            path,
            factory.make_name("keyring"),
        )

    def test_injects_default_keyring_if_passed(self):
        path = "streams/v1/index.json.gpg"
        content = factory.make_string()
        keyring = factory.make_name("keyring")
        self.patch(helpers, "policy_read_signed")
        policy = helpers.get_signing_policy(path, keyring)
        policy(content, path)
        helpers.policy_read_signed.assert_called_once_with(
            content, path, keyring=keyring
        )


class TestGetOSFromProduct(MAASTestCase):
    """Tests for `get_os_from_product`."""

    def test_returns_os_from_product(self):
        os = factory.make_name("os")
        product = {"os": os}
        self.assertEqual(os, helpers.get_os_from_product(product))

    def test_returns_ubuntu_if_missing(self):
        self.assertEqual("ubuntu", helpers.get_os_from_product({}))
