# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for the KeySource model."""


import random

from maasserver.enum import KEYS_PROTOCOL_TYPE
import maasserver.models.keysource as keysource_module
from maasserver.models.keysource import KeySource
from maasserver.models.sshkey import SSHKey
from maasserver.testing import get_data
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase


class TestKeySource(MAASServerTestCase):
    """Testing for the :class:`KeySource`."""

    def test_import_keys_with_no_keys(self):
        user = factory.make_User()
        protocol = random.choice(
            [KEYS_PROTOCOL_TYPE.LP, KEYS_PROTOCOL_TYPE.GH]
        )
        auth_id = factory.make_name("auth_id")
        keysource = factory.make_KeySource(protocol, auth_id)
        mock_get_protocol_keys = self.patch(
            keysource_module, "get_protocol_keys"
        )
        mock_get_protocol_keys.return_value = []
        keysource.import_keys(user)
        mock_get_protocol_keys.assert_called_once_with(protocol, auth_id)
        self.assertFalse(SSHKey.objects.all().exists())

    def test_import_keys_with_keys(self):
        user = factory.make_User()
        protocol = random.choice(
            [KEYS_PROTOCOL_TYPE.LP, KEYS_PROTOCOL_TYPE.GH]
        )
        auth_id = factory.make_name("auth_id")
        keysource = factory.make_KeySource(protocol, auth_id)
        keys = get_data("data/test_rsa0.pub") + get_data("data/test_rsa1.pub")
        mock_get_protocol_keys = self.patch(
            keysource_module, "get_protocol_keys"
        )
        mock_get_protocol_keys.return_value = keys.strip().split("\n")
        returned_sshkeys = keysource.import_keys(user)
        mock_get_protocol_keys.assert_called_once_with(protocol, auth_id)
        self.assertEqual(SSHKey.objects.count(), 2)
        self.assertCountEqual(
            returned_sshkeys, SSHKey.objects.filter(keysource=keysource)
        )

    def test_import_keys_source_exists_adds_new_keys(self):
        user = factory.make_User()
        protocol = random.choice(
            [KEYS_PROTOCOL_TYPE.LP, KEYS_PROTOCOL_TYPE.GH]
        )
        auth_id = factory.make_name("auth_id")
        keysource = factory.make_KeySource(protocol, auth_id)
        keys = get_data("data/test_rsa0.pub") + get_data("data/test_rsa1.pub")
        mock_get_protocol_keys = self.patch(
            keysource_module, "get_protocol_keys"
        )
        mock_get_protocol_keys.return_value = keys.strip().split("\n")
        keysource.import_keys(user)
        # Add a new key
        keys += get_data("data/test_rsa2.pub")
        mock_get_protocol_keys.return_value = keys.strip().split("\n")
        returned_sshkeys = keysource.import_keys(user)
        self.assertEqual(3, SSHKey.objects.count())
        self.assertCountEqual(
            returned_sshkeys, SSHKey.objects.filter(keysource=keysource)
        )

    def test_import_keys_source_exists_doesnt_remove_keys(self):
        user = factory.make_User()
        protocol = random.choice(
            [KEYS_PROTOCOL_TYPE.LP, KEYS_PROTOCOL_TYPE.GH]
        )
        auth_id = factory.make_name("auth_id")
        keysource = factory.make_KeySource(protocol, auth_id)
        keys = get_data("data/test_rsa0.pub") + get_data("data/test_rsa1.pub")
        mock_get_protocol_keys = self.patch(
            keysource_module, "get_protocol_keys"
        )
        mock_get_protocol_keys.return_value = keys.strip().split("\n")
        returned_sshkeys = keysource.import_keys(user)
        # only return one key
        keys = get_data("data/test_rsa0.pub")
        mock_get_protocol_keys.return_value = keys.strip().split("\n")
        keysource.import_keys(user)
        # no key is removed
        self.assertEqual(2, SSHKey.objects.count())
        self.assertCountEqual(
            returned_sshkeys, SSHKey.objects.filter(keysource=keysource)
        )


class TestKeySourceManager(MAASServerTestCase):
    """Testing for the:class:`KeySourceManager` model manager."""

    def test_save_keys_for_user_imports_keys(self):
        user = factory.make_User()
        protocol = random.choice(
            [KEYS_PROTOCOL_TYPE.LP, KEYS_PROTOCOL_TYPE.GH]
        )
        auth_id = factory.make_name("auth_id")
        mock_import_keys = self.patch(KeySource, "import_keys")
        KeySource.objects.save_keys_for_user(user, protocol, auth_id)
        mock_import_keys.assert_called_once_with(user)
        self.assertEqual(KeySource.objects.count(), 1)

    def test_save_keys_for_user_does_not_create_duplicate_keysource(self):
        user = factory.make_User()
        protocol = random.choice(
            [KEYS_PROTOCOL_TYPE.LP, KEYS_PROTOCOL_TYPE.GH]
        )
        auth_id = factory.make_name("auth_id")
        factory.make_KeySource(protocol=protocol, auth_id=auth_id)
        mock_import_keys = self.patch(KeySource, "import_keys")
        KeySource.objects.save_keys_for_user(user, protocol, auth_id)
        mock_import_keys.assert_called_once_with(user)
        self.assertEqual(KeySource.objects.count(), 1)
