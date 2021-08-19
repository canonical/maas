# Copyright 2020 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for maas_certificates."""


from datetime import datetime, timedelta
import os
from socket import gethostname

from OpenSSL import crypto

from maastesting.fixtures import TempDirectory
from maastesting.matchers import MockCalledOnce, MockNotCalled
from maastesting.testcase import MAASTestCase
from provisioningserver import maas_certificates
from provisioningserver.utils.fs import NamedLock


class TestGenerateCertificate(MAASTestCase):
    def test_generate_certificate(self):
        cert = maas_certificates.generate_certificate("maas")
        self.assertIsInstance(cert.cert, crypto.X509)
        self.assertIsInstance(cert.key, crypto.PKey)
        self.assertEqual(cert.cert.get_subject().CN, "maas")
        self.assertEqual(
            crypto.dump_publickey(crypto.FILETYPE_PEM, cert.cert.get_pubkey()),
            crypto.dump_publickey(crypto.FILETYPE_PEM, cert.key),
        )
        self.assertEqual(cert.key.bits(), 4096)
        self.assertEqual(cert.key.type(), crypto.TYPE_RSA)
        self.assertGreaterEqual(
            datetime.utcnow() + timedelta(days=3650),
            cert.expiration(),
        )

    def test_generate_certificate_key_bits(self):
        cert = maas_certificates.generate_certificate("maas", key_bits=1024)
        self.assertEqual(cert.key.bits(), 1024)

    def test_generate_certificate_validity(self):
        cert = maas_certificates.generate_certificate(
            "maas", validity=timedelta(days=100)
        )
        self.assertGreaterEqual(
            datetime.utcnow() + timedelta(days=100),
            cert.expiration(),
        )


class TestCertificate(MAASTestCase):
    def test_certificate(self):
        cert = maas_certificates.generate_certificate("maas")
        self.assertEqual(cert.cn(), "maas")
        self.assertGreaterEqual(
            datetime.utcnow() + timedelta(days=3650),
            cert.expiration(),
        )
        self.assertTrue(
            cert.certificate_pem().startswith("-----BEGIN CERTIFICATE-----")
        )
        self.assertTrue(
            cert.public_key_pem().startswith("-----BEGIN PUBLIC KEY-----")
        )
        self.assertTrue(
            cert.private_key_pem().startswith("-----BEGIN PRIVATE KEY-----")
        )

    def test_from_pem_string(self):
        cert = maas_certificates.generate_certificate("maas")
        material = cert.certificate_pem() + cert.private_key_pem()
        other_cert = maas_certificates.Certificate.from_pem(material)
        self.assertEqual(cert.certificate_pem(), other_cert.certificate_pem())
        self.assertEqual(cert.private_key_pem(), other_cert.private_key_pem())

    def test_from_pem_bytes(self):
        cert = maas_certificates.generate_certificate("maas")
        material = bytes(
            cert.certificate_pem() + cert.private_key_pem(), "ascii"
        )
        other_cert = maas_certificates.Certificate.from_pem(material)
        self.assertEqual(cert.certificate_pem(), other_cert.certificate_pem())
        self.assertEqual(cert.private_key_pem(), other_cert.private_key_pem())


class TestMAASCertificates(MAASTestCase):
    def setUp(self):
        super().setUp()
        self.certificates_dir = self.useFixture(TempDirectory()).path
        self.orig_maas_private_key = maas_certificates.MAAS_PRIVATE_KEY
        maas_certificates.MAAS_PRIVATE_KEY = os.path.join(
            self.certificates_dir, "maas.key"
        )
        self.orig_maas_public_key = maas_certificates.MAAS_PUBLIC_KEY
        maas_certificates.MAAS_PUBLIC_KEY = os.path.join(
            self.certificates_dir, "maas.pub"
        )
        self.orig_maas_certificate = maas_certificates.MAAS_CERTIFICATE
        maas_certificates.MAAS_CERTIFICATE = os.path.join(
            self.certificates_dir, "maas.crt"
        )
        maas_certificates._cert_not_before = None
        maas_certificates._cert_not_after = None
        maas_certificates._cert_mtime = None

    def tearDown(self):
        super().tearDown()
        maas_certificates.MAAS_PRIVATE_KEY = self.orig_maas_private_key
        maas_certificates.MAAS_PUBLIC_KEY = self.orig_maas_public_key
        maas_certificates.MAAS_CERTIFICATE = self.orig_maas_certificate

    def test_generate_rsa_if_needed(self):
        self.assertTrue(maas_certificates.generate_rsa_keys_if_needed())
        self.assertTrue(os.path.exists(maas_certificates.MAAS_PRIVATE_KEY))
        self.assertTrue(os.path.exists(maas_certificates.MAAS_PUBLIC_KEY))
        self.assertFalse(os.path.exists(maas_certificates.MAAS_CERTIFICATE))

    def test_generate_rsa_if_needed_does_nothing(self):
        mock_pkey = self.patch(maas_certificates.crypto, "PKey")
        open(maas_certificates.MAAS_PRIVATE_KEY, "w").close()
        self.assertFalse(maas_certificates.generate_rsa_keys_if_needed())
        self.assertThat(mock_pkey, MockNotCalled())

    def test_generate_rsa_if_needed_waits_for_creation(self):
        mock_isfile = self.patch(maas_certificates.os.path, "isfile")
        mock_isfile.side_effect = [False, False, True, True]
        mock_sleep = self.patch(maas_certificates, "sleep")
        with NamedLock("RSA"):
            self.assertTrue(maas_certificates.generate_rsa_keys_if_needed())
        self.assertThat(mock_sleep, MockCalledOnce())

    def test_generate_rsa_if_needed_raises_exception_on_failure(self):
        self.patch(maas_certificates, "sleep")
        with NamedLock("RSA"):
            self.assertRaises(
                AssertionError, maas_certificates.generate_rsa_keys_if_needed
            )

    def test_generate_certificate_if_needed(self):
        self.assertTrue(maas_certificates.generate_certificate_if_needed())
        self.assertTrue(os.path.exists(maas_certificates.MAAS_PRIVATE_KEY))
        self.assertTrue(os.path.exists(maas_certificates.MAAS_PUBLIC_KEY))
        self.assertTrue(os.path.exists(maas_certificates.MAAS_CERTIFICATE))
        with open(maas_certificates.MAAS_CERTIFICATE) as f:
            cert = crypto.load_certificate(crypto.FILETYPE_PEM, f.read())
        self.assertEqual(gethostname(), cert.get_subject().CN)
        self.assertGreaterEqual(
            datetime.utcnow(),
            datetime.strptime(cert.get_notBefore().decode(), "%Y%m%d%H%M%SZ"),
        )
        self.assertGreaterEqual(
            datetime.strptime(cert.get_notAfter().decode(), "%Y%m%d%H%M%SZ"),
            datetime.utcnow() + timedelta(days=364),
        )

    def test_generate_certificate_if_needed_checks_cache(self):
        now = datetime.utcnow()
        mock_isfile = self.patch(maas_certificates.os.path, "isfile")
        mock_isfile.return_value = True
        mock_getmtime = self.patch(maas_certificates.os.path, "getmtime")
        mock_getmtime.return_value = now
        mock_open = self.patch(maas_certificates, "open")
        maas_certificates._cert_not_before = now - timedelta(days=182)
        maas_certificates._cert_not_after = now + timedelta(days=182)
        maas_certificates._cert_mtime = now
        self.assertFalse(maas_certificates.generate_certificate_if_needed())
        self.assertThat(mock_open, MockNotCalled())

    def test_generate_certificate_if_needed_regenerates_if_before(self):
        maas_certificates.generate_certificate_if_needed(not_before=60 * 60)
        old_hash = maas_certificates.get_certificate_fingerprint()
        self.assertTrue(maas_certificates.generate_certificate_if_needed())
        new_hash = maas_certificates.get_certificate_fingerprint()
        self.assertNotEquals(old_hash, new_hash)

    def test_generate_certificate_if_needed_regenerates_if_after(self):
        maas_certificates.generate_certificate_if_needed(not_after=-1)
        old_hash = maas_certificates.get_certificate_fingerprint()
        self.assertTrue(maas_certificates.generate_certificate_if_needed())
        new_hash = maas_certificates.get_certificate_fingerprint()
        self.assertNotEquals(old_hash, new_hash)

    def test_generate_certificate_if_needed_does_nothing_if_valid(self):
        maas_certificates.generate_certificate_if_needed()
        old_hash = maas_certificates.get_certificate_fingerprint()
        self.assertFalse(maas_certificates.generate_certificate_if_needed())
        new_hash = maas_certificates.get_certificate_fingerprint()
        self.assertEqual(old_hash, new_hash)

    def test_generate_certificate_if_needed_raises_exception_on_failure(self):
        self.patch(maas_certificates, "sleep")
        with NamedLock("certificate"):
            self.assertRaises(
                AssertionError,
                maas_certificates.generate_certificate_if_needed,
            )

    def test_get_maas_cert_tuple(self):
        self.assertItemsEqual(
            (
                maas_certificates.MAAS_CERTIFICATE,
                maas_certificates.MAAS_PRIVATE_KEY,
            ),
            maas_certificates.get_maas_cert_tuple(),
        )
        self.assertTrue(os.path.isfile(maas_certificates.MAAS_CERTIFICATE))
        self.assertTrue(os.path.isfile(maas_certificates.MAAS_PRIVATE_KEY))
