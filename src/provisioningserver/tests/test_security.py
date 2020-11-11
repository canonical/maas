# Copyright 2014-2017 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for MAAS's cluster security module."""


import binascii
from binascii import b2a_hex
from pathlib import Path
from random import randint
import time
from unittest.mock import sentinel

from cryptography.fernet import InvalidToken
from testtools import ExpectedException
from testtools.matchers import Equals, IsInstance

from maastesting.factory import factory
from maastesting.matchers import MockCalledOnceWith
from maastesting.testcase import MAASTestCase
from provisioningserver import security
from provisioningserver.path import get_maas_data_path
from provisioningserver.security import (
    fernet_decrypt_psk,
    fernet_encrypt_psk,
    MissingSharedSecret,
)


class SharedSecretTestCase(MAASTestCase):
    def setUp(self):
        """Ensures each test starts cleanly, with no pre-existing secret."""
        get_secret = self.patch(security, "get_shared_secret_filesystem_path")
        # Ensure each test uses a different filename for the shared secret,
        # so that tests cannot interfere with each other.
        get_secret.return_value = Path(
            get_maas_data_path("secret-%s" % factory.make_string(16))
        )
        # Extremely unlikely, but just in case.
        self.delete_secret()
        self.addCleanup(
            setattr,
            security,
            "DEFAULT_ITERATION_COUNT",
            security.DEFAULT_ITERATION_COUNT,
        )
        # The default high iteration count would make the tests very slow.
        security.DEFAULT_ITERATION_COUNT = 2
        super().setUp()

    def tearDown(self):
        self.delete_secret()
        super().tearDown()

    def delete_secret(self):
        security._fernet_psk = None
        secret_file = security.get_shared_secret_filesystem_path()
        if secret_file.exists():
            secret_file.unlink()

    def write_secret(self):
        secret = factory.make_bytes()
        secret_path = security.get_shared_secret_filesystem_path()
        secret_path.parent.mkdir(parents=True, exist_ok=True)
        secret_path.write_text(security.to_hex(secret))
        return secret


class TestGetSharedSecretFromFilesystem(SharedSecretTestCase):
    def test_returns_None_when_no_secret_exists(self):
        self.assertIsNone(security.get_shared_secret_from_filesystem())

    def test_returns_secret_when_one_exists(self):
        secret = self.write_secret()
        self.assertEqual(secret, security.get_shared_secret_from_filesystem())

    def test_same_secret_is_returned_on_subsequent_calls(self):
        self.write_secret()
        self.assertEqual(
            security.get_shared_secret_from_filesystem(),
            security.get_shared_secret_from_filesystem(),
        )

    def test_errors_reading_file_are_raised(self):
        self.write_secret()
        secret_path = security.get_shared_secret_filesystem_path()
        secret_path.chmod(0o000)
        self.assertRaises(IOError, security.get_shared_secret_from_filesystem)

    def test_errors_when_filesystem_value_cannot_be_decoded(self):
        self.write_secret()
        security.get_shared_secret_filesystem_path().write_text("_")
        self.assertRaises(
            binascii.Error, security.get_shared_secret_from_filesystem
        )

    def test_deals_fine_with_whitespace_in_filesystem_value(self):
        secret = self.write_secret()
        security.get_shared_secret_filesystem_path().write_text(
            " %s\n" % security.to_hex(secret),
        )
        self.assertEqual(secret, security.get_shared_secret_from_filesystem())

    def test_reads_with_lock(self):
        mock_file_lock = self.patch_autospec(security, "FileLock")
        security.set_shared_secret_on_filesystem(b"foo")
        security.get_shared_secret_from_filesystem()
        mock_file_lock.assert_called()


class TestSetSharedSecretOnFilesystem(MAASTestCase):
    def test_default_iteration_count_is_reasonably_large(self):
        # Ensure that the iteration count is high by default. This is very
        # important so that the MAAS secret cannot be determined by
        # brute-force.
        self.assertThat(security.DEFAULT_ITERATION_COUNT, Equals(100000))

    def read_secret(self):
        secret_path = security.get_shared_secret_filesystem_path()
        secret_hex = secret_path.read_text()
        return security.to_bin(secret_hex)

    def test_writes_secret(self):
        secret = factory.make_bytes()
        security.set_shared_secret_on_filesystem(secret)
        self.assertEqual(secret, self.read_secret())

    def test_writes_with_lock(self):
        mock_file_lock = self.patch_autospec(security, "FileLock")
        security.set_shared_secret_on_filesystem(b"foo")
        mock_file_lock.assert_called()

    def test_writes_with_secure_permissions(self):
        secret = factory.make_bytes()
        security.set_shared_secret_on_filesystem(secret)
        secret_path = security.get_shared_secret_filesystem_path()
        perms_observed = secret_path.stat().st_mode & 0o777
        perms_expected = 0o640
        self.assertEqual(
            perms_expected,
            perms_observed,
            "Expected %04o, got %04o." % (perms_expected, perms_observed),
        )


class TestInstallSharedSecretScript(MAASTestCase):
    def test_has_add_arguments(self):
        # It doesn't do anything, but it's there to fulfil the contract with
        # ActionScript/MainScript.
        security.InstallSharedSecretScript.add_arguments(sentinel.parser)
        self.assertIsNotNone("Obligatory assertion.")

    def installAndCheckExitCode(self, code):
        error = self.assertRaises(
            SystemExit, security.InstallSharedSecretScript.run, sentinel.args
        )
        self.assertEqual(code, error.code)

    def test_reads_secret_from_stdin(self):
        secret = factory.make_bytes()

        stdin = self.patch_autospec(security, "stdin")
        stdin.readline.return_value = b2a_hex(secret).decode("ascii")
        stdin.isatty.return_value = False

        self.installAndCheckExitCode(0)
        self.assertEqual(secret, security.get_shared_secret_from_filesystem())

    def test_ignores_surrounding_whitespace_from_stdin(self):
        secret = factory.make_bytes()

        stdin = self.patch_autospec(security, "stdin")
        stdin.readline.return_value = (
            " " + b2a_hex(secret).decode("ascii") + " \n"
        )
        stdin.isatty.return_value = False

        self.installAndCheckExitCode(0)
        self.assertEqual(secret, security.get_shared_secret_from_filesystem())

    def test_reads_secret_from_tty(self):
        secret = factory.make_bytes()

        stdin = self.patch_autospec(security, "stdin")
        stdin.isatty.return_value = True

        input = self.patch(security, "input")
        input.return_value = b2a_hex(secret).decode("ascii")

        self.installAndCheckExitCode(0)
        self.assertThat(
            input, MockCalledOnceWith("Secret (hex/base16 encoded): ")
        )
        self.assertEqual(secret, security.get_shared_secret_from_filesystem())

    def test_ignores_surrounding_whitespace_from_tty(self):
        secret = factory.make_bytes()

        stdin = self.patch_autospec(security, "stdin")
        stdin.isatty.return_value = True

        input = self.patch(security, "input")
        input.return_value = " " + b2a_hex(secret).decode("ascii") + " \n"

        self.installAndCheckExitCode(0)
        self.assertEqual(secret, security.get_shared_secret_from_filesystem())

    def test_deals_gracefully_with_eof_from_tty(self):
        stdin = self.patch_autospec(security, "stdin")
        stdin.isatty.return_value = True

        input = self.patch(security, "input")
        input.side_effect = EOFError()

        self.installAndCheckExitCode(1)
        self.assertIsNone(security.get_shared_secret_from_filesystem())

    def test_deals_gracefully_with_interrupt_from_tty(self):
        stdin = self.patch_autospec(security, "stdin")
        stdin.isatty.return_value = True

        input = self.patch(security, "input")
        input.side_effect = KeyboardInterrupt()

        self.assertRaises(
            KeyboardInterrupt,
            security.InstallSharedSecretScript.run,
            sentinel.args,
        )
        self.assertIsNone(security.get_shared_secret_from_filesystem())

    def test_prints_error_message_when_secret_cannot_be_decoded(self):
        stdin = self.patch_autospec(security, "stdin")
        stdin.readline.return_value = "garbage"
        stdin.isatty.return_value = False

        print = self.patch(security, "print")

        self.installAndCheckExitCode(1)
        self.assertThat(
            print,
            MockCalledOnceWith(
                "Secret could not be decoded:",
                "Odd-length string",
                file=security.stderr,
            ),
        )

    def test_prints_message_when_secret_is_installed(self):
        stdin = self.patch_autospec(security, "stdin")
        stdin.readline.return_value = b2a_hex(factory.make_bytes()).decode(
            "ascii"
        )
        stdin.isatty.return_value = False

        print = self.patch(security, "print")

        self.installAndCheckExitCode(0)
        shared_secret_path = security.get_shared_secret_filesystem_path()
        self.assertThat(
            print,
            MockCalledOnceWith("Secret installed to %s." % shared_secret_path),
        )


class TestCheckForSharedSecretScript(MAASTestCase):
    def test_has_add_arguments(self):
        # It doesn't do anything, but it's there to fulfil the contract with
        # ActionScript/MainScript.
        security.CheckForSharedSecretScript.add_arguments(sentinel.parser)
        self.assertIsNotNone("Obligatory assertion.")

    def test_exits_non_zero_if_secret_does_not_exist(self):
        print = self.patch(security, "print")
        error = self.assertRaises(
            SystemExit, security.CheckForSharedSecretScript.run, sentinel.args
        )
        self.assertEqual(1, error.code)
        self.assertThat(
            print, MockCalledOnceWith("Shared-secret is NOT installed.")
        )

    def test_exits_zero_if_secret_exists(self):
        security.set_shared_secret_on_filesystem(factory.make_bytes())
        print = self.patch(security, "print")
        error = self.assertRaises(
            SystemExit, security.CheckForSharedSecretScript.run, sentinel.args
        )
        self.assertEqual(0, error.code)
        self.assertThat(
            print, MockCalledOnceWith("Shared-secret is installed.")
        )


class TestFernetEncryption(SharedSecretTestCase):
    def test_first_encrypt_caches_psk(self):
        self.write_secret()
        self.assertIsNone(security._fernet_psk)
        testdata = factory.make_string()
        fernet_encrypt_psk(testdata)
        self.assertIsNotNone(security._fernet_psk)

    def test_derives_identical_key_on_decrypt(self):
        self.write_secret()
        self.assertIsNone(security._fernet_psk)
        testdata = factory.make_bytes()
        token = fernet_encrypt_psk(testdata)
        first_key = security._fernet_psk
        # Make it seem like we're decrypting something without ever encrypting
        # anything first.
        security._fernet_psk = None
        decrypted = fernet_decrypt_psk(token)
        second_key = security._fernet_psk
        self.assertEqual(first_key, second_key)
        self.assertEqual(testdata, decrypted)

    def test_can_encrypt_and_decrypt_string(self):
        self.write_secret()
        testdata = factory.make_string()
        token = fernet_encrypt_psk(testdata)
        # Round-trip this to a string, since Fernet tokens are used inside
        # strings (such as JSON objects) typically.
        token = token.decode("ascii")
        decrypted = fernet_decrypt_psk(token)
        decrypted = decrypted.decode("ascii")
        self.assertThat(decrypted, Equals(testdata))

    def test_can_encrypt_and_decrypt_with_raw_bytes(self):
        self.write_secret()
        testdata = factory.make_bytes()
        token = fernet_encrypt_psk(testdata, raw=True)
        self.assertThat(token, IsInstance(bytes))
        decrypted = fernet_decrypt_psk(token, raw=True)
        self.assertThat(decrypted, Equals(testdata))

    def test_can_encrypt_and_decrypt_bytes(self):
        self.write_secret()
        testdata = factory.make_bytes()
        token = fernet_encrypt_psk(testdata)
        decrypted = fernet_decrypt_psk(token)
        self.assertThat(decrypted, Equals(testdata))

    def test_raises_when_no_secret_exists(self):
        testdata = factory.make_bytes()
        with ExpectedException(MissingSharedSecret):
            fernet_encrypt_psk(testdata)
        with ExpectedException(MissingSharedSecret):
            fernet_decrypt_psk(b"")

    def test_assures_data_integrity(self):
        self.write_secret()
        testdata = factory.make_bytes(size=10)
        token = fernet_encrypt_psk(testdata)
        bad_token = bytearray(token)
        # Flip a bit in the token, so we can ensure it won't decrypt if it
        # has been corrupted. Subtract 4 to avoid the end of the token; that
        # portion is just padding, and isn't covered by the HMAC.
        byte_to_flip = randint(0, len(bad_token) - 4)
        bit_to_flip = 1 << randint(0, 7)
        bad_token[byte_to_flip] ^= bit_to_flip
        bad_token = bytes(bad_token)
        test_description = "token=%s; token[%d] ^= 0x%02x" % (
            token.decode("utf-8"),
            byte_to_flip,
            bit_to_flip,
        )
        with ExpectedException(InvalidToken, msg=test_description):
            fernet_decrypt_psk(bad_token)

    def test_messages_from_up_to_a_minute_in_the_future_accepted(self):
        self.write_secret()
        testdata = factory.make_bytes()
        now = time.time()
        self.patch(time, "time").side_effect = [now + 60, now]
        token = fernet_encrypt_psk(testdata)
        fernet_decrypt_psk(token, ttl=1)

    def test_messages_from_the_past_exceeding_ttl_rejected(self):
        self.write_secret()
        testdata = factory.make_bytes()
        now = time.time()
        self.patch(time, "time").side_effect = [now - 2, now]
        token = fernet_encrypt_psk(testdata)
        with ExpectedException(InvalidToken):
            fernet_decrypt_psk(token, ttl=1)

    def test_messages_from_future_exceeding_clock_skew_limit_rejected(self):
        self.write_secret()
        testdata = factory.make_bytes()
        now = time.time()
        self.patch(time, "time").side_effect = [now + 61, now]
        token = fernet_encrypt_psk(testdata)
        with ExpectedException(InvalidToken):
            fernet_decrypt_psk(token, ttl=1)
