# Copyright 2012-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

import random

from django.core.exceptions import ValidationError

from maasserver.enum import KEYS_PROTOCOL_TYPE
from maasserver.models import SSHKey, sshkey
from maasserver.models.sshkey import validate_ssh_public_key
from maasserver.testing import get_data
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase


class TestSSHKeyValidator(MAASServerTestCase):
    def test_validates_rsa_public_key(self):
        key_string = get_data("data/test_rsa0.pub")
        validate_ssh_public_key(key_string)
        # No ValidationError.

    def test_validates_dsa_public_key(self):
        key_string = get_data("data/test_dsa.pub")
        validate_ssh_public_key(key_string)
        # No ValidationError.

    def test_validates_ecdsa_curve256_public_key(self):
        key_string = get_data("data/test_ecdsa256.pub")
        validate_ssh_public_key(key_string)
        # No ValidationError.

    def test_validates_ecdsa_curve384_public_key(self):
        key_string = get_data("data/test_ecdsa384.pub")
        validate_ssh_public_key(key_string)
        # No ValidationError.

    def test_validates_ecdsa_curve521_public_key(self):
        key_string = get_data("data/test_ecdsa521.pub")
        validate_ssh_public_key(key_string)
        # No ValidationError.

    def test_validates_ed25519_public_key(self):
        key_string = get_data("data/test_ed25519.pub")
        validate_ssh_public_key(key_string)
        # No ValidationError.

    def test_does_not_validate_random_data(self):
        key_string = factory.make_string()
        self.assertRaises(ValidationError, validate_ssh_public_key, key_string)

    def test_does_not_validate_wrongly_padded_data(self):
        key_string = "ssh-dss {} {}@{}".format(
            factory.make_string(),
            factory.make_string(),
            factory.make_string(),
        )
        self.assertRaises(ValidationError, validate_ssh_public_key, key_string)

    def test_does_not_validate_non_ascii_key(self):
        non_ascii_key = "AAB3NzaC" + "\u2502" + "mN6Lo2I9w=="
        key_string = "ssh-rsa {} {}@{}".format(
            non_ascii_key,
            factory.make_string(),
            factory.make_string(),
        )
        self.assertRaises(ValidationError, validate_ssh_public_key, key_string)

    def test_does_not_validate_wrong_key(self):
        # Validation fails if normalise_openssh_public_key crashes.
        norm = self.patch(sshkey, "normalise_openssh_public_key")
        norm.side_effect = factory.make_exception_type()
        self.assertRaises(
            ValidationError, validate_ssh_public_key, factory.make_name("key")
        )

    def test_does_not_validate_rsa_private_key(self):
        key_string = get_data("data/test_rsa")
        self.assertRaises(ValidationError, validate_ssh_public_key, key_string)

    def test_does_not_validate_dsa_private_key(self):
        key_string = get_data("data/test_dsa")
        self.assertRaises(ValidationError, validate_ssh_public_key, key_string)


class TestSSHKey(MAASServerTestCase):
    def test_sshkey_validation_with_valid_key(self):
        key_string = get_data("data/test_rsa0.pub")
        user = factory.make_User()
        key = SSHKey(key=key_string, user=user)
        key.full_clean()
        # No ValidationError.

    def test_sshkey_validation_fails_if_key_is_invalid(self):
        key_string = factory.make_string()
        user = factory.make_User()
        key = SSHKey(key=key_string, user=user)
        self.assertRaises(ValidationError, key.full_clean)

    def test_sshkey_user_and_key_unique_together_create(self):
        protocol = random.choice(
            [KEYS_PROTOCOL_TYPE.LP, KEYS_PROTOCOL_TYPE.GH]
        )
        auth_id = factory.make_name("auth_id")
        key_string = get_data("data/test_rsa0.pub")
        user = factory.make_User()
        key = SSHKey(
            key=key_string, user=user, protocol=protocol, auth_id=auth_id
        )
        key.save()
        key2 = SSHKey(
            key=key_string, user=user, protocol=protocol, auth_id=auth_id
        )
        self.assertRaises(ValidationError, key2.full_clean)

    def test_sshkey_user_and_key_unique_together_change_key(self):
        protocol = random.choice(
            [KEYS_PROTOCOL_TYPE.LP, KEYS_PROTOCOL_TYPE.GH]
        )
        auth_id = factory.make_name("auth_id")
        key_string1 = get_data("data/test_rsa1.pub")
        key_string2 = get_data("data/test_rsa2.pub")
        user = factory.make_User()
        key1 = SSHKey(
            key=key_string1, user=user, protocol=protocol, auth_id=auth_id
        )
        key1.save()
        key2 = SSHKey(
            key=key_string2, user=user, protocol=protocol, auth_id=auth_id
        )
        key2.save()
        key2.key = key1.key
        self.assertRaises(ValidationError, key2.full_clean)

    def test_sshkey_same_key_can_be_used_by_different_sources(self):
        auth_id = factory.make_name("auth_id")
        key_string = get_data("data/test_rsa0.pub")
        user = factory.make_User()
        key1 = SSHKey(
            key=key_string,
            user=user,
            protocol=KEYS_PROTOCOL_TYPE.LP,
            auth_id=auth_id,
        )
        key1.save()
        key2 = SSHKey(
            key=key_string,
            user=user,
            protocol=KEYS_PROTOCOL_TYPE.GH,
            auth_id=auth_id,
        )
        key2.save()
        self.assertIsNone(key2.full_clean())

    def test_sshkey_same_key_can_be_used_by_different_users(self):
        key_string = get_data("data/test_rsa0.pub")
        user = factory.make_User()
        key = SSHKey(key=key_string, user=user)
        key.save()
        user2 = factory.make_User()
        key2 = SSHKey(key=key_string, user=user2)
        key2.full_clean()
        # No ValidationError.


class TestSSHKeyManager(MAASServerTestCase):
    def test_get_keys_for_user_no_keys(self):
        user = factory.make_User()
        keys = SSHKey.objects.get_keys_for_user(user)
        self.assertCountEqual([], keys)

    def test_get_keys_for_user_with_keys(self):
        user1, created_keys = factory.make_user_with_keys(
            n_keys=3, username="user1"
        )
        # user2
        factory.make_user_with_keys(n_keys=2)
        keys = SSHKey.objects.get_keys_for_user(user1)
        self.assertCountEqual([key.key for key in created_keys], keys)
