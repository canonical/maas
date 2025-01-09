# Copyright 2012-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

import random

from django.core.exceptions import ValidationError
from django.utils.safestring import SafeString

from maasserver.enum import KEYS_PROTOCOL_TYPE
from maasserver.models import SSHKey, sshkey
import maasserver.models.sshkey as sshkey_module
from maasserver.models.sshkey import (
    get_html_display_for_key,
    HELLIPSIS,
    validate_ssh_public_key,
)
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


class TestGetHTMLDisplayForKey(MAASServerTestCase):
    def make_comment(self, length):
        """Create a comment of the desired length.

        The comment may contain spaces, but not begin or end in them.  It
        will be of the desired length both before and after stripping.
        """
        return "".join(
            [
                factory.make_string(1),
                factory.make_string(max([length - 2, 0]), spaces=True),
                factory.make_string(1),
            ]
        )[:length]

    def make_key(self, type_len=7, key_len=360, comment_len=None):
        """Produce a fake ssh public key containing arbitrary data.

        :param type_len: The length of the "key type" field.  (Default is
            sized for the real-life "ssh-rsa").
        :param key_len: Length of the key text.  (With a roughly realistic
            default).
        :param comment_len: Length of the comment field.  The comment may
            contain spaces.  Leave it None to omit the comment.
        :return: A string representing the combined key-file contents.
        """
        fields = [factory.make_string(type_len), factory.make_string(key_len)]
        if comment_len is not None:
            fields.append(self.make_comment(comment_len))
        return " ".join(fields)

    def test_display_returns_unchanged_if_unknown_and_small(self):
        # If the key does not look like a normal key (with three parts
        # separated by spaces, it's returned unchanged if its size is <=
        # size.
        size = random.randint(101, 200)
        key = factory.make_string(size - 100)
        display = get_html_display_for_key(key, size)
        self.assertLess(len(display), size)
        self.assertEqual(key, display)

    def test_display_returns_cropped_if_unknown_and_large(self):
        # If the key does not look like a normal key (with three parts
        # separated by spaces, it's returned cropped if its size is >
        # size.
        size = random.randint(20, 100)  # size cannot be < len(HELLIPSIS).
        key = factory.make_string(size + 1)
        display = get_html_display_for_key(key, size)
        self.assertEqual(size, len(display))
        self.assertEqual(
            "%.*s%s" % (size - len(HELLIPSIS), key, HELLIPSIS), display
        )

    def test_display_escapes_commentless_key_for_html(self):
        # The key's comment may contain characters that are not safe for
        # including in HTML, and so get_html_display_for_key escapes the
        # text.
        # There are several code paths in get_html_display_for_key; this
        # test is for the case where the key has no comment, and is
        # brief enough to fit into the allotted space.
        self.assertEqual(
            "&lt;type&gt; &lt;text&gt;",
            get_html_display_for_key("<type> <text>", 100),
        )

    def test_display_escapes_short_key_for_html(self):
        # The key's comment may contain characters that are not safe for
        # including in HTML, and so get_html_display_for_key escapes the
        # text.
        # There are several code paths in get_html_display_for_key; this
        # test is for the case where the whole key is short enough to
        # fit completely into the output.
        key = "<type> <text> <comment>"
        display = get_html_display_for_key(key, 100)
        # This also verifies that the entire key fits into the string.
        # Otherwise we might accidentally get one of the other cases.
        self.assertTrue(display.endswith("&lt;comment&gt;"))
        # And of course the check also implies that the text is
        # HTML-escaped:
        self.assertNotIn("<", display)
        self.assertNotIn(">", display)

    def test_display_escapes_long_key_for_html(self):
        # The key's comment may contain characters that are not safe for
        # including in HTML, and so get_html_display_for_key escapes the
        # text.
        # There are several code paths in get_html_display_for_key; this
        # test is for the case where the comment is short enough to fit
        # completely into the output.
        key = "<type> %s <comment>" % ("<&>" * 50)
        display = get_html_display_for_key(key, 50)
        # This verifies that we are indeed getting an abbreviated
        # display.  Otherwise we might accidentally get one of the other
        # cases.
        self.assertIn("&hellip;", display)
        self.assertIn("comment", display)
        # And now, on to checking that the text is HTML-safe.
        self.assertNotIn("<", display)
        self.assertNotIn(">", display)
        self.assertTrue(display.endswith("&lt;comment&gt;"))

    def test_display_limits_size_with_large_comment(self):
        # If the key has a large 'comment' part, the key is simply
        # cropped and HELLIPSIS appended to it.
        key = self.make_key(10, 10, 100)
        display = get_html_display_for_key(key, 50)
        self.assertEqual(50, len(display))
        self.assertEqual(
            "%.*s%s" % (50 - len(HELLIPSIS), key, HELLIPSIS), display
        )

    def test_display_limits_size_with_large_key_type(self):
        # If the key has a large 'key_type' part, the key is simply
        # cropped and HELLIPSIS appended to it.
        key = self.make_key(100, 10, 10)
        display = get_html_display_for_key(key, 50)
        self.assertEqual(50, len(display))
        self.assertEqual(
            "%.*s%s" % (50 - len(HELLIPSIS), key, HELLIPSIS), display
        )

    def test_display_cropped_key(self):
        # If the key has a small key_type, a small comment and a large
        # key_string (which is the 'normal' case), the key_string part
        # gets cropped.
        type_len = 10
        comment_len = 10
        key = self.make_key(type_len, 100, comment_len)
        key_type, key_string, comment = key.split(" ", 2)
        display = get_html_display_for_key(key, 50)
        self.assertEqual(50, len(display))
        self.assertEqual(
            "%s %.*s%s %s"
            % (
                key_type,
                50 - (type_len + len(HELLIPSIS) + comment_len + 2),
                key_string,
                HELLIPSIS,
                comment,
            ),
            display,
        )


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

    def test_sshkey_display_with_real_life_key(self):
        # With a real-life ssh-rsa key, the key_string part is cropped.
        key_string = get_data("data/test_rsa0.pub")
        user = factory.make_User()
        key = SSHKey(key=key_string, user=user)
        display = key.display_html()
        self.assertEqual(
            "ssh-rsa AAAAB3NzaC1yc&hellip; ubuntu@test_rsa0.pub", display
        )

    def test_sshkey_display_is_marked_as_HTML_safe(self):
        key_string = get_data("data/test_rsa0.pub")
        user = factory.make_User()
        key = SSHKey(key=key_string, user=user)
        display = key.display_html()
        self.assertIsInstance(display, SafeString)

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

    def test_import_keys_with_no_keys(self):
        user = factory.make_User()
        protocol = random.choice(
            [KEYS_PROTOCOL_TYPE.LP, KEYS_PROTOCOL_TYPE.GH]
        )
        auth_id = factory.make_name("auth_id")
        mock_get_protocol_keys = self.patch(sshkey_module, "get_protocol_keys")
        mock_get_protocol_keys.return_value = []
        SSHKey.objects.from_keysource(user, protocol, auth_id)
        mock_get_protocol_keys.assert_called_once_with(protocol, auth_id)
        self.assertFalse(SSHKey.objects.all().exists())

    def test_import_keys_with_keys(self):
        user = factory.make_User()
        protocol = random.choice(
            [KEYS_PROTOCOL_TYPE.LP, KEYS_PROTOCOL_TYPE.GH]
        )
        auth_id = factory.make_name("auth_id")
        keys = get_data("data/test_rsa0.pub") + get_data("data/test_rsa1.pub")
        mock_get_protocol_keys = self.patch(sshkey_module, "get_protocol_keys")
        mock_get_protocol_keys.return_value = keys.strip().split("\n")
        returned_sshkeys = SSHKey.objects.from_keysource(
            user, protocol, auth_id
        )
        mock_get_protocol_keys.assert_called_once_with(protocol, auth_id)
        self.assertEqual(SSHKey.objects.count(), 2)
        self.assertCountEqual(
            returned_sshkeys,
            SSHKey.objects.filter(protocol=protocol, auth_id=auth_id),
        )

    def test_import_keys_source_exists_doesnt_remove_keys(self):
        user = factory.make_User()
        protocol = random.choice(
            [KEYS_PROTOCOL_TYPE.LP, KEYS_PROTOCOL_TYPE.GH]
        )
        auth_id = factory.make_name("auth_id")
        keys = get_data("data/test_rsa0.pub") + get_data("data/test_rsa1.pub")
        mock_get_protocol_keys = self.patch(sshkey_module, "get_protocol_keys")
        mock_get_protocol_keys.return_value = keys.strip().split("\n")
        returned_sshkeys = SSHKey.objects.from_keysource(
            user, protocol, auth_id
        )
        # only return one key
        keys = get_data("data/test_rsa0.pub")
        mock_get_protocol_keys.return_value = keys.strip().split("\n")
        SSHKey.objects.from_keysource(user, protocol, auth_id)
        # no key is removed
        self.assertEqual(2, SSHKey.objects.count())
        self.assertCountEqual(
            returned_sshkeys,
            SSHKey.objects.filter(protocol=protocol, auth_id=auth_id),
        )
