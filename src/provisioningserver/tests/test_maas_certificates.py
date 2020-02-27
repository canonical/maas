# Copyright 2020 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for maas_certificates."""

__all__ = []

from datetime import datetime, timedelta
import os
from socket import gethostname

from OpenSSL import crypto

from maastesting.fixtures import TempDirectory
from maastesting.matchers import MockCalledOnce, MockNotCalled
from maastesting.testcase import MAASTestCase
from provisioningserver import maas_certificates
from provisioningserver.utils.fs import NamedLock


class TestMAASCertificates(MAASTestCase):
    def setUp(self):
        super().setUp()
        self.certificates_dir = self.useFixture(TempDirectory()).path
        maas_certificates.MAAS_PRIVATE_KEY = os.path.join(
            self.certificates_dir, "maas.key"
        )
        maas_certificates.MAAS_PUBLIC_KEY = os.path.join(
            self.certificates_dir, "maas.pub"
        )
        maas_certificates.MAAS_CERTIFICATE = os.path.join(
            self.certificates_dir, "maas.crt"
        )

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
        self.assertEquals(gethostname(), cert.get_subject().CN)
        self.assertGreaterEqual(
            datetime.utcnow(),
            datetime.strptime(cert.get_notBefore().decode(), "%Y%m%d%H%M%SZ"),
        )
        self.assertGreaterEqual(
            datetime.strptime(cert.get_notAfter().decode(), "%Y%m%d%H%M%SZ"),
            datetime.utcnow() + timedelta(days=364),
        )

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
        self.assertEquals(old_hash, new_hash)

    def test_generate_certificate_if_needed_waits_for_creation(self):
        mock_isfile = self.patch(maas_certificates.os.path, "isfile")
        mock_isfile.side_effect = [False, False, False, True, True]
        mock_sleep = self.patch(maas_certificates, "sleep")
        with NamedLock("certificate"):
            self.assertTrue(maas_certificates.generate_certificate_if_needed())
        self.assertThat(mock_sleep, MockCalledOnce())

    def test_generate_certificate_if_needed_raises_exception_on_failure(self):
        self.patch(maas_certificates, "sleep")
        with NamedLock("certificate"):
            self.assertRaises(
                AssertionError,
                maas_certificates.generate_certificate_if_needed,
            )
