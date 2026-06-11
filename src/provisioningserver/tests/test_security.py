# Copyright 2014-2017 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for MAAS's cluster security module."""

from binascii import b2a_hex
from pathlib import Path
from random import randint
import time
from unittest.mock import patch, sentinel

from cryptography.exceptions import InvalidTag

from maastesting.factory import factory
from maastesting.testcase import MAASTestCase
from provisioningserver import security
from provisioningserver.security import (
    decrypt_psk,
    encrypt_psk,
    MissingSharedSecret,
)
from provisioningserver.utils import env as utils_env
from provisioningserver.utils.env import MAAS_SECRET


class SharedSecretTestCase(MAASTestCase):
    def setUp(self):
        MAAS_SECRET.set(None)
        self.patch(security, "_aes_psk", value=None)
        self.addCleanup(
            setattr,
            security,
            "DEFAULT_ITERATION_COUNT",
            security.DEFAULT_ITERATION_COUNT,
        )
        # The default high iteration count would make the tests very slow.
        security.DEFAULT_ITERATION_COUNT = 2
        super().setUp()


class TestInstallSharedSecretScript(MAASTestCase):
    def setUp(self):
        # Ensure each test uses a different filename for the shared secret,
        # so that tests cannot interfere with each other.
        super().setUp()
        tempdir = Path(self.make_dir())
        utils_env.MAAS_SHARED_SECRET.clear_cached()
        self.patch(
            utils_env.MAAS_SHARED_SECRET, "_path", lambda: tempdir / "secret"
        )
        self._mock_print = self.patch(security, "print")

    def read_secret_from_fs(self):
        secret = utils_env.MAAS_SHARED_SECRET.get()
        return security.to_bin(secret) if secret else None

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
        self.assertEqual(self.read_secret_from_fs(), secret)

    def test_ignores_surrounding_whitespace_from_stdin(self):
        secret = factory.make_bytes()

        stdin = self.patch_autospec(security, "stdin")
        stdin.readline.return_value = (
            " " + b2a_hex(secret).decode("ascii") + " \n"
        )
        stdin.isatty.return_value = False

        self.installAndCheckExitCode(0)
        self.assertEqual(self.read_secret_from_fs(), secret)

    def test_reads_secret_from_tty(self):
        secret = factory.make_bytes()

        stdin = self.patch_autospec(security, "stdin")
        stdin.isatty.return_value = True

        input = self.patch(security, "input")
        input.return_value = b2a_hex(secret).decode("ascii")

        self.installAndCheckExitCode(0)
        input.assert_called_once_with("Secret (hex/base16 encoded): ")
        self.assertEqual(self.read_secret_from_fs(), secret)

    def test_ignores_surrounding_whitespace_from_tty(self):
        secret = factory.make_bytes()

        stdin = self.patch_autospec(security, "stdin")
        stdin.isatty.return_value = True

        input = self.patch(security, "input")
        input.return_value = " " + b2a_hex(secret).decode("ascii") + " \n"

        self.installAndCheckExitCode(0)
        self.assertEqual(self.read_secret_from_fs(), secret)

    def test_deals_gracefully_with_eof_from_tty(self):
        stdin = self.patch_autospec(security, "stdin")
        stdin.isatty.return_value = True

        input = self.patch(security, "input")
        input.side_effect = EOFError()

        self.installAndCheckExitCode(1)
        self.assertIsNone(self.read_secret_from_fs())

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
        self.assertIsNone(self.read_secret_from_fs())

    def test_prints_error_message_when_secret_cannot_be_decoded(self):
        stdin = self.patch_autospec(security, "stdin")
        stdin.readline.return_value = "garbage"
        stdin.isatty.return_value = False

        self.installAndCheckExitCode(1)
        self._mock_print.assert_called_once_with(
            "Secret could not be decoded:",
            "Odd-length string",
            file=security.stderr,
        )

    def test_prints_message_when_secret_is_installed(self):
        stdin = self.patch_autospec(security, "stdin")
        stdin.readline.return_value = b2a_hex(factory.make_bytes()).decode(
            "ascii"
        )
        stdin.isatty.return_value = False

        self.installAndCheckExitCode(0)
        self._mock_print.assert_called_once_with(
            f"Secret installed to {utils_env.MAAS_SHARED_SECRET.path}."
        )


class TestAESEncryption(SharedSecretTestCase):
    def setUp(self):
        super().setUp()
        MAAS_SECRET.set(factory.make_bytes())

    def test_first_encrypt_caches_psk(self):
        self.assertIsNone(security._aes_psk)
        testdata = factory.make_string()
        encrypt_psk(testdata)
        self.assertIsNotNone(security._aes_psk)

    def test_derives_identical_key_on_decrypt(self):
        self.assertIsNone(security._aes_psk)
        testdata = factory.make_bytes()
        token = encrypt_psk(testdata)
        first_key = security._aes_psk
        # Make it seem like we're decrypting something without ever encrypting
        # anything first.
        security._aes_psk = None
        decrypted = decrypt_psk(token)
        second_key = security._aes_psk
        self.assertEqual(first_key, second_key)
        self.assertEqual(testdata, decrypted)

    def test_can_encrypt_and_decrypt_string(self):
        testdata = factory.make_string()
        token = encrypt_psk(testdata)
        # Round-trip this to a string, since tokens are used inside
        # strings (such as JSON objects) typically.
        token = token.decode("ascii")
        decrypted = decrypt_psk(token)
        decrypted = decrypted.decode("ascii")
        self.assertEqual(testdata, decrypted)

    def test_can_encrypt_and_decrypt_with_raw_bytes(self):
        testdata = factory.make_bytes()
        token = encrypt_psk(testdata, raw=True)
        self.assertIsInstance(token, bytes)
        decrypted = decrypt_psk(token, raw=True)
        self.assertEqual(testdata, decrypted)

    def test_can_encrypt_and_decrypt_bytes(self):
        testdata = factory.make_bytes()
        token = encrypt_psk(testdata)
        decrypted = decrypt_psk(token)
        self.assertEqual(testdata, decrypted)

    def test_raises_when_no_secret_exists(self):
        MAAS_SECRET.set(None)
        testdata = factory.make_bytes()
        with self.assertRaisesRegex(
            MissingSharedSecret, "MAAS shared secret not found"
        ):
            encrypt_psk(testdata)
        with self.assertRaisesRegex(
            MissingSharedSecret, "MAAS shared secret not found"
        ):
            decrypt_psk(b"")

    def test_messages_from_the_past_exceeding_ttl_rejected(self):
        testdata = factory.make_bytes()
        with patch(
            "provisioningserver.security.time.time",
            return_value=time.time() - 2,
        ):
            token = encrypt_psk(testdata)
        self.assertRaises(ValueError, decrypt_psk, token, ttl=1)

    def test_messages_from_recent_past_within_ttl_accepted(self):
        testdata = factory.make_bytes()
        now = time.time()
        with patch(
            "provisioningserver.security.time.time", return_value=now - 30
        ):
            token = encrypt_psk(testdata)
        with patch("provisioningserver.security.time.time", return_value=now):
            decrypted = decrypt_psk(token, ttl=60)
        self.assertEqual(testdata, decrypted)

    def test_messages_from_future_exceeding_clock_skew_limit_rejected(self):
        testdata = factory.make_bytes()
        now = time.time()
        with patch(
            "provisioningserver.security.time.time", return_value=now + 61
        ):
            token = encrypt_psk(testdata)
        with patch("provisioningserver.security.time.time", return_value=now):
            self.assertRaises(ValueError, decrypt_psk, token)

    def test_assures_data_integrity(self):
        testdata = factory.make_bytes(size=10)
        token = encrypt_psk(testdata)
        bad_token = bytearray(token)
        # Flip a bit in the token to ensure it won't decrypt if corrupted.
        byte_to_flip = randint(0, len(bad_token) - 1)
        bit_to_flip = 1 << randint(0, 7)
        bad_token[byte_to_flip] ^= bit_to_flip
        bad_token = bytes(bad_token)
        with self.assertRaises((InvalidTag, ValueError)):
            decrypt_psk(bad_token)
