# Copyright 2022 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test the config-tls command."""

from contextlib import contextmanager
import tempfile

from django.core.management import call_command

from maasserver.management.commands import config_tls
from maasserver.models import Config
from maasserver.testing.testcase import MAASServerTestCase
from provisioningserver.certificates import CertificateError
from provisioningserver.testing.certificates import get_sample_cert


class TestConfigTLSCommand(MAASServerTestCase):
    def setUp(self):
        super().setUp()
        self.read_input = self.patch(config_tls, "read_input")
        self.read_input.return_value = ""

    @contextmanager
    def wrong_file(self):
        with tempfile.NamedTemporaryFile(mode="w+") as key_file:
            key_file.flush()
            yield key_file.name

    def _get_config(self):
        return Config.objects.get_configs(["tls_key", "tls_cert", "tls_port"])

    def test_config_tls_disable(self):
        call_command("config_tls", "disable")
        self.assertEqual(
            {"tls_port": None, "tls_key": "", "tls_cert": ""},
            self._get_config(),
        )

    def test_config_tls_enable(self):
        sample_cert = get_sample_cert()
        cert_path, key_path = sample_cert.tempfiles()

        self.read_input.return_value = "y"
        call_command("config_tls", "enable", key_path, cert_path, "-p=5234")

        self.assertEqual(
            {
                "tls_port": 5234,
                "tls_key": sample_cert.private_key_pem(),
                "tls_cert": sample_cert.certificate_pem(),
            },
            self._get_config(),
        )

    def test_config_tls_enable_break(self):
        sample_cert = get_sample_cert()
        cert_path, key_path = sample_cert.tempfiles()

        last_config = self._get_config()

        call_command("config_tls", "enable", key_path, cert_path)
        self.read_input.return_value = "n"

        current_config = self._get_config()
        self.assertEqual(last_config, current_config)

    def test_config_tls_enable_with_default_port(self):
        sample_cert = get_sample_cert()
        cert_path, key_path = sample_cert.tempfiles()

        self.read_input.return_value = "y"
        call_command("config_tls", "enable", key_path, cert_path)

        self.assertEqual(
            {
                "tls_port": 5443,
                "tls_key": sample_cert.private_key_pem(),
                "tls_cert": sample_cert.certificate_pem(),
            },
            self._get_config(),
        )

    def test_config_tls_enable_with_incorrect_key(self):
        with self.wrong_file() as key_path:
            sample_cert = get_sample_cert()
            cert_path, _ = sample_cert.tempfiles()

            self.read_input.return_value = "y"
            error = self.assertRaises(
                CertificateError,
                call_command,
                "config_tls",
                "enable",
                key_path,
                cert_path,
            )
            self.assertEqual("Invalid PEM material", str(error))

    def test_config_tls_enable_with_incorrect_cert(self):
        with self.wrong_file() as cert_path:
            sample_cert = get_sample_cert()
            _, key_path = sample_cert.tempfiles()

            self.read_input.return_value = "y"
            error = self.assertRaises(
                CertificateError,
                call_command,
                "config_tls",
                "enable",
                key_path,
                cert_path,
            )
            self.assertEqual("Invalid PEM material", str(error))
