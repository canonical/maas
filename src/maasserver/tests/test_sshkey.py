# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for the SSHKey model."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = []

import random

from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.utils.safestring import SafeUnicode
from maasserver.models import SSHKey
from maasserver.models.sshkey import (
    get_html_display_for_key,
    HELLIPSIS,
    validate_ssh_public_key,
    )
from maasserver.testing import get_data
from maasserver.testing.factory import factory
from maasserver.testing.testcase import TestCase
from testtools.matchers import EndsWith


class SSHKeyValidatorTest(TestCase):

    def test_validates_rsa_public_key(self):
        key_string = get_data('data/test_rsa0.pub')
        validate_ssh_public_key(key_string)
        # No ValidationError.

    def test_validates_dsa_public_key(self):
        key_string = get_data('data/test_dsa.pub')
        validate_ssh_public_key(key_string)
        # No ValidationError.

    def test_does_not_validate_random_data(self):
        key_string = factory.getRandomString()
        self.assertRaises(
            ValidationError, validate_ssh_public_key, key_string)

    def test_does_not_validate_wrongly_padded_data(self):
        key_string = 'ssh-dss %s %s@%s' % (
            factory.getRandomString(), factory.getRandomString(),
            factory.getRandomString())
        self.assertRaises(
            ValidationError, validate_ssh_public_key, key_string)

    def test_does_not_validate_rsa_private_key(self):
        key_string = get_data('data/test_rsa')
        self.assertRaises(
            ValidationError, validate_ssh_public_key, key_string)

    def test_does_not_validate_dsa_private_key(self):
        key_string = get_data('data/test_dsa')
        self.assertRaises(
            ValidationError, validate_ssh_public_key, key_string)


class GetHTMLDisplayForKeyTest(TestCase):
    """Testing for the method `get_html_display_for_key`."""

    def make_comment(self, length):
        """Create a comment of the desired length.

        The comment may contain spaces, but not begin or end in them.  It
        will be of the desired length both before and after stripping.
        """
        return ''.join([
            factory.getRandomString(1),
            factory.getRandomString(max([length - 2, 0]), spaces=True),
            factory.getRandomString(1),
            ])[:length]

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
        fields = [
            factory.getRandomString(type_len),
            factory.getRandomString(key_len),
            ]
        if comment_len is not None:
            fields.append(self.make_comment(comment_len))
        return " ".join(fields)

    def test_display_returns_unchanged_if_unknown_and_small(self):
        # If the key does not look like a normal key (with three parts
        # separated by spaces, it's returned unchanged if its size is <=
        # size.
        size = random.randint(101, 200)
        key = factory.getRandomString(size - 100)
        display = get_html_display_for_key(key, size)
        self.assertTrue(len(display) < size)
        self.assertEqual(key, display)

    def test_display_returns_cropped_if_unknown_and_large(self):
        # If the key does not look like a normal key (with three parts
        # separated by spaces, it's returned cropped if its size is >
        # size.
        size = random.randint(20, 100)  # size cannot be < len(HELLIPSIS).
        key = factory.getRandomString(size + 1)
        display = get_html_display_for_key(key, size)
        self.assertEqual(size, len(display))
        self.assertEqual(
            '%.*s%s' % (size - len(HELLIPSIS), key, HELLIPSIS), display)

    def test_display_escapes_commentless_key_for_html(self):
        # The key's comment may contain characters that are not safe for
        # including in HTML, and so get_html_display_for_key escapes the
        # text.
        # There are several code paths in get_html_display_for_key; this
        # test is for the case where the key has no comment, and is
        # brief enough to fit into the allotted space.
        self.assertEqual(
            "&lt;type&gt; &lt;text&gt;",
            get_html_display_for_key("<type> <text>", 100))

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
        self.assertThat(display, EndsWith("&lt;comment&gt;"))
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
        self.assertThat(display, EndsWith("&lt;comment&gt;"))

    def test_display_limits_size_with_large_comment(self):
        # If the key has a large 'comment' part, the key is simply
        # cropped and HELLIPSIS appended to it.
        key = self.make_key(10, 10, 100)
        display = get_html_display_for_key(key, 50)
        self.assertEqual(50, len(display))
        self.assertEqual(
            '%.*s%s' % (50 - len(HELLIPSIS), key, HELLIPSIS), display)

    def test_display_limits_size_with_large_key_type(self):
        # If the key has a large 'key_type' part, the key is simply
        # cropped and HELLIPSIS appended to it.
        key = self.make_key(100, 10, 10)
        display = get_html_display_for_key(key, 50)
        self.assertEqual(50, len(display))
        self.assertEqual(
            '%.*s%s' % (50 - len(HELLIPSIS), key, HELLIPSIS), display)

    def test_display_cropped_key(self):
        # If the key has a small key_type, a small comment and a large
        # key_string (which is the 'normal' case), the key_string part
        # gets cropped.
        type_len = 10
        comment_len = 10
        key = self.make_key(type_len, 100, comment_len)
        key_type, key_string, comment = key.split(' ', 2)
        display = get_html_display_for_key(key, 50)
        self.assertEqual(50, len(display))
        self.assertEqual(
            '%s %.*s%s %s' % (
                key_type,
                50 - (type_len + len(HELLIPSIS) + comment_len + 2),
                key_string, HELLIPSIS, comment),
            display)


class SSHKeyTest(TestCase):
    """Testing for the :class:`SSHKey`."""

    def test_sshkey_validation_with_valid_key(self):
        key_string = get_data('data/test_rsa0.pub')
        user = factory.make_user()
        key = SSHKey(key=key_string, user=user)
        key.full_clean()
        # No ValidationError.

    def test_sshkey_validation_fails_if_key_is_invalid(self):
        key_string = factory.getRandomString()
        user = factory.make_user()
        key = SSHKey(key=key_string, user=user)
        self.assertRaises(
            ValidationError, key.full_clean)

    def test_sshkey_display_with_real_life_key(self):
        # With a real-life ssh-rsa key, the key_string part is cropped.
        key_string = get_data('data/test_rsa0.pub')
        user = factory.make_user()
        key = SSHKey(key=key_string, user=user)
        display = key.display_html()
        self.assertEqual(
            'ssh-rsa AAAAB3NzaC1yc2E&hellip; ubuntu@server-7476', display)

    def test_sshkey_display_is_marked_as_HTML_safe(self):
        key_string = get_data('data/test_rsa0.pub')
        user = factory.make_user()
        key = SSHKey(key=key_string, user=user)
        display = key.display_html()
        self.assertIsInstance(display, SafeUnicode)

    def test_sshkey_user_and_key_unique_together(self):
        key_string = get_data('data/test_rsa0.pub')
        user = factory.make_user()
        key = SSHKey(key=key_string, user=user)
        key.save()
        key2 = SSHKey(key=key_string, user=user)
        self.assertRaises(
            ValidationError, key2.full_clean)

    def test_sshkey_user_and_key_unique_together_db_level(self):
        # Even if we hack our way around model-level checks, uniqueness
        # of the user/key combination is enforced at the database level.
        key_string = get_data('data/test_rsa0.pub')
        user = factory.make_user()
        existing_key = SSHKey(key=key_string, user=user)
        existing_key.save()
        # The trick to hack around the model-level checks: create a
        # duplicate key for another user, then attach it to the same
        # user as the existing key by updating it directly in the
        # database.
        redundant_key = SSHKey(key=key_string, user=factory.make_user())
        redundant_key.save()
        self.assertRaises(
            IntegrityError,
            SSHKey.objects.filter(id=redundant_key.id).update,
            user=user)

    def test_sshkey_same_key_can_be_used_by_different_users(self):
        key_string = get_data('data/test_rsa0.pub')
        user = factory.make_user()
        key = SSHKey(key=key_string, user=user)
        key.save()
        user2 = factory.make_user()
        key2 = SSHKey(key=key_string, user=user2)
        key2.full_clean()
        # No ValidationError.


class SSHKeyManagerTest(TestCase):
    """Testing for the :class:`SSHKeyManager` model manager."""

    def test_get_keys_for_user_no_keys(self):
        user = factory.make_user()
        keys = SSHKey.objects.get_keys_for_user(user)
        self.assertItemsEqual([], keys)

    def test_get_keys_for_user_with_keys(self):
        user1, created_keys = factory.make_user_with_keys(
            n_keys=3, username='user1')
        # user2
        factory.make_user_with_keys(n_keys=2)
        keys = SSHKey.objects.get_keys_for_user(user1)
        self.assertItemsEqual([key.key for key in created_keys], keys)
