# Copyright 2014-2016 Canonical Ltd.
# Copyright 2014 Cloudbase Solutions SRL.
# This software is licensed under the GNU Affero General Public License
# version 3 (see the file LICENSE).

"""Tests for `maasserver.x509`."""


import os

import OpenSSL
from testtools.matchers import FileExists

from maasserver import x509
from maasserver.x509 import WinRMX509, WinRMX509Error
from maastesting.factory import factory
from maastesting.matchers import FileContains, MockCalledOnceWith
from maastesting.testcase import MAASTestCase


class TestWinRMX509(MAASTestCase):
    def configure_WinRMX509(self):
        cert_name = factory.make_name("cert_name")
        upn_name = factory.make_name("upn_name")
        cert_dir = self.make_dir()
        winrmx509 = WinRMX509(
            cert_name=cert_name, upn_name=upn_name, cert_dir=cert_dir
        )
        return winrmx509

    def make_certificate(self):
        winrmx509 = self.configure_WinRMX509()
        _, cert = winrmx509.get_key_and_cert()
        winrmx509.write_cert(cert)
        return cert, winrmx509

    def dump_certificate(self, cert):
        return OpenSSL.crypto.dump_certificate(
            OpenSSL.crypto.FILETYPE_PEM, cert
        )

    def make_privatekey(self):
        winrmx509 = self.configure_WinRMX509()
        key, _ = winrmx509.get_key_and_cert()
        winrmx509.write_privatekey(key)
        return key, winrmx509

    def dump_privatekey(self, key):
        return OpenSSL.crypto.dump_privatekey(OpenSSL.crypto.FILETYPE_PEM, key)

    def make_cert_and_privatekey(self):
        winrmx509 = self.configure_WinRMX509()
        key, cert = winrmx509.get_key_and_cert()
        winrmx509.write_cert(cert)
        winrmx509.write_privatekey(key)
        return key, cert, winrmx509

    def test_create_cert_raises_error_on_file_already_exists(self):
        cert, winrmx509 = self.make_certificate()
        self.assertRaises(WinRMX509Error, winrmx509.create_cert)

    def test_create_cert_writes_cert(self):
        winrmx509 = self.configure_WinRMX509()
        winrmx509.create_cert()
        self.assertThat(winrmx509.pem_file, FileExists())

    def test_create_cert_writes_privatekey(self):
        winrmx509 = self.configure_WinRMX509()
        winrmx509.create_cert()
        self.assertThat(winrmx509.key_file, FileExists())

    def test_create_cert_exports_p12(self):
        winrmx509 = self.configure_WinRMX509()
        winrmx509.create_cert()
        self.assertThat(winrmx509.pfx_file, FileExists())

    def test_create_cert_raises_error_on_export_p12_error(self):
        winrmx509 = self.configure_WinRMX509()
        self.patch(winrmx509, "export_p12").side_effect = OpenSSL.crypto.Error
        self.assertRaises(WinRMX509Error, winrmx509.create_cert)

    def test_create_cert_calls_print_cert_details(self):
        winrmx509 = self.configure_WinRMX509()
        mock_print = self.patch(winrmx509, "print_cert_details")
        winrmx509.create_cert(print_cert=True)
        self.assertThat(mock_print, MockCalledOnceWith(winrmx509.pem_file))

    def test_get_key_and_cert_returns_rsa_key(self):
        winrmx509 = self.configure_WinRMX509()
        key, _ = winrmx509.get_key_and_cert()
        self.assertEqual(OpenSSL.crypto.TYPE_RSA, key.type())

    def test_get_key_and_cert_returns_key_of_correct_size(self):
        winrmx509 = self.configure_WinRMX509()
        key, _ = winrmx509.get_key_and_cert()
        self.assertEqual(winrmx509.KEY_SIZE, key.bits())

    def test_get_key_and_cert_returns_cert_with_upn_name(self):
        winrmx509 = self.configure_WinRMX509()
        _, cert = winrmx509.get_key_and_cert()
        self.assertEqual(winrmx509.upn_name, cert.get_subject().CN)

    def test_get_key_and_cert_returns_cert_with_valid_serial_number(self):
        winrmx509 = self.configure_WinRMX509()
        _, cert = winrmx509.get_key_and_cert()
        self.assertEqual(1000, cert.get_serial_number())

    def test_get_key_and_cert_returns_cert_with_extensions(self):
        winrmx509 = self.configure_WinRMX509()
        _, cert = winrmx509.get_key_and_cert()
        self.assertEqual(2, cert.get_extension_count())
        self.assertEqual(
            b"subjectAltName", cert.get_extension(0).get_short_name()
        )
        self.assertEqual(
            b"extendedKeyUsage", cert.get_extension(1).get_short_name()
        )

    def test_get_key_and_cert_returns_cert_with_issuer_set_from_subject(self):
        winrmx509 = self.configure_WinRMX509()
        _, cert = winrmx509.get_key_and_cert()
        self.assertEqual(cert.get_subject(), cert.get_issuer())

    def test_get_cert_details(self):
        cert, winrmx509 = self.make_certificate()
        self.assertEqual(
            {
                "subject": cert.get_subject().CN,
                "thumbprint": cert.digest("SHA1"),
                "contents": self.dump_certificate(cert).decode("utf-8"),
            },
            winrmx509.get_cert_details(winrmx509.pem_file),
        )

    def test_write_privatekey(self):
        key, winrmx509 = self.make_privatekey()
        self.assertThat(
            winrmx509.key_file, FileContains(self.dump_privatekey(key))
        )

    def test_write_cert(self):
        cert, winrmx509 = self.make_certificate()
        self.assertThat(
            winrmx509.pem_file, FileContains(self.dump_certificate(cert))
        )

    def test_load_pem_file_returns_cert_and_contents(self):
        cert, winrmx509 = self.make_certificate()
        loaded_cert, contents = winrmx509.load_pem_file(winrmx509.pem_file)
        self.assertEqual(self.dump_certificate(cert), contents.encode("ascii"))
        self.assertEqual(
            self.dump_certificate(cert), self.dump_certificate(loaded_cert)
        )

    def test_load_pem_file_raises_error_on_invalid_cert(self):
        winrmx509 = self.configure_WinRMX509()
        self.patch(x509, "read_text_file").return_value = factory.make_string()
        self.assertRaises(WinRMX509Error, winrmx509.load_pem_file, "file")

    def test_export_p12(self):
        key, cert, winrmx509 = self.make_cert_and_privatekey()
        passphrase = factory.make_name("password")
        winrmx509.export_p12(key, cert, passphrase)
        with open(winrmx509.pfx_file, "rb") as stream:
            p12_contents = stream.read()
        p12 = OpenSSL.crypto.load_pkcs12(
            p12_contents, bytes(passphrase.encode("utf-8"))
        )
        self.assertEqual(
            self.dump_certificate(cert),
            self.dump_certificate(p12.get_certificate()),
        )
        self.assertEqual(
            self.dump_privatekey(key),
            self.dump_privatekey(p12.get_privatekey()),
        )

    def test_get_ssl_dir_ensures_directory_exists(self):
        winrmx509 = self.configure_WinRMX509()
        makedirs = self.patch(x509, "makedirs")
        fake_dir = factory.make_name("dir")
        winrmx509.get_ssl_dir(fake_dir)
        self.assertThat(makedirs, MockCalledOnceWith(fake_dir, exist_ok=True))

    def test_get_ssl_dir_returns_home_ssl_dir(self):
        winrmx509 = self.configure_WinRMX509()
        self.patch(x509, "makedirs")
        self.assertEqual(
            os.path.join(os.path.expanduser("~"), ".ssl"),
            winrmx509.get_ssl_dir(),
        )

    def test_generate_passphrase(self):
        winrmx509 = self.configure_WinRMX509()
        self.assertEqual(
            winrmx509.PASSPHRASE_LENGTH, len(winrmx509.generate_passphrase())
        )
