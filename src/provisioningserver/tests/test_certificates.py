# Copyright 2020 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from datetime import datetime, timedelta
from pathlib import Path

from fixtures import EnvironmentVariable, TempDir
from OpenSSL import crypto

from maastesting.testcase import MAASTestCase
from provisioningserver.certificates import (
    Certificate,
    generate_certificate,
    get_maas_cert_tuple,
)


class TestGenerateCertificate(MAASTestCase):
    def test_generate_certificate(self):
        cert = generate_certificate("maas")
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
        cert = generate_certificate("maas", key_bits=1024)
        self.assertEqual(cert.key.bits(), 1024)

    def test_generate_certificate_validity(self):
        cert = generate_certificate("maas", validity=timedelta(days=100))
        self.assertGreaterEqual(
            datetime.utcnow() + timedelta(days=100),
            cert.expiration(),
        )


class TestCertificate(MAASTestCase):
    def test_certificate(self):
        cert = generate_certificate("maas")
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
        cert = generate_certificate("maas")
        material = cert.certificate_pem() + cert.private_key_pem()
        other_cert = Certificate.from_pem(material)
        self.assertEqual(cert.certificate_pem(), other_cert.certificate_pem())
        self.assertEqual(cert.private_key_pem(), other_cert.private_key_pem())

    def test_from_pem_bytes(self):
        cert = generate_certificate("maas")
        material = bytes(
            cert.certificate_pem() + cert.private_key_pem(), "ascii"
        )
        other_cert = Certificate.from_pem(material)
        self.assertEqual(cert.certificate_pem(), other_cert.certificate_pem())
        self.assertEqual(cert.private_key_pem(), other_cert.private_key_pem())


class TestGetMAASCertTuple(MAASTestCase):
    def setUp(self):
        super().setUp()
        self.tempdir = Path(self.useFixture(TempDir()).path)

    def test_get_maas_cert_tuple_missing_files(self):
        self.useFixture(EnvironmentVariable("MAAS_ROOT", str(self.tempdir)))
        self.useFixture(EnvironmentVariable("SNAP", None))
        self.assertIsNone(get_maas_cert_tuple())

    def test_get_maas_cert_tuple(self):
        certs_dir = self.tempdir / "etc/maas/certificates"
        certs_dir.mkdir(parents=True)
        (certs_dir / "maas.crt").touch()
        (certs_dir / "maas.key").touch()
        self.useFixture(EnvironmentVariable("MAAS_ROOT", str(self.tempdir)))
        self.useFixture(EnvironmentVariable("SNAP", None))
        self.assertEqual(
            get_maas_cert_tuple(),
            (
                f"{certs_dir}/maas.crt",
                f"{certs_dir}/maas.key",
            ),
        )

    def test_get_maas_cert_tuple_snap(self):
        certs_dir = self.tempdir / "certificates"
        certs_dir.mkdir(parents=True)
        (certs_dir / "maas.crt").touch()
        (certs_dir / "maas.key").touch()
        self.useFixture(EnvironmentVariable("SNAP_COMMON", str(self.tempdir)))
        self.useFixture(EnvironmentVariable("SNAP", "/snap/maas/current"))
        self.assertEqual(
            get_maas_cert_tuple(),
            (
                f"{certs_dir}/maas.crt",
                f"{certs_dir}/maas.key",
            ),
        )
