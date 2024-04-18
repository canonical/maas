from unittest.mock import Mock
from uuid import uuid4

from OpenSSL import crypto

from maasserver.models import Config
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
import maasserver.utils.certificates as certificates
from maasserver.utils.certificates import (
    certificate_generated_by_this_maas,
    generate_ca_certificate,
    generate_certificate,
    get_maas_client_cn,
    get_ssl_certificate,
)
from provisioningserver.certificates import Certificate
from provisioningserver.utils.testing import MAASUUIDFixture


class TestGetMAASClientCN(MAASServerTestCase):
    def test_with_object(self):
        Config.objects.set_config("maas_name", "my-maas")
        object_name = "my-object"
        self.assertEqual("my-object@my-maas", get_maas_client_cn(object_name))

    def test_with_object_long_name(self):
        Config.objects.set_config("maas_name", "my-maas")
        object_name = factory.make_string(size=60)
        truncated_name = object_name[:56]
        self.assertEqual(
            f"{truncated_name}@my-maas", get_maas_client_cn(object_name)
        )

    def test_no_object(self):
        Config.objects.set_config("maas_name", "my-maas")
        self.assertEqual("my-maas", get_maas_client_cn(None))


class TestGenerateCertificate(MAASServerTestCase):
    def test_generate_certificate(self):
        mock_cert = self.patch_autospec(certificates, "Certificate")
        maas_uuid = str(uuid4())
        self.useFixture(MAASUUIDFixture(maas_uuid))
        generate_certificate("maas")
        mock_cert.generate.assert_called_once_with(
            "maas",
            organization_name="MAAS",
            organizational_unit_name=maas_uuid,
        )


class TestGenerateCACertificate(MAASServerTestCase):
    def test_generate_ca_certificate(self):
        mock_cert = self.patch_autospec(certificates, "Certificate")
        maas_uuid = str(uuid4())
        self.useFixture(MAASUUIDFixture(maas_uuid))
        generate_ca_certificate("maas")
        mock_cert.generate_ca_certificate.assert_called_once_with(
            "maas",
            organization_name="MAAS",
            organizational_unit_name=maas_uuid,
        )


class TestGenerateSignedCertificate(MAASServerTestCase):
    def test_generate_ca_certificate(self):
        mock_cert_request = self.patch_autospec(
            certificates, "CertificateRequest"
        )
        maas_uuid = str(uuid4())
        self.useFixture(MAASUUIDFixture(maas_uuid))
        ca = Mock()
        certificates.generate_signed_certificate(ca, "maas")
        mock_cert_request.generate.assert_called_once()
        ca.sign_certificate_request.assert_called_once()


class TestCertificateGeneratedByThisMAAS(MAASServerTestCase):
    def setUp(self):
        super().setUp()
        self.maas_uuid = str(uuid4())
        self.useFixture(MAASUUIDFixture(self.maas_uuid))
        ssl_cert = crypto.X509()
        self._issuer = ssl_cert.get_issuer()
        self._cert = Certificate(None, ssl_cert, ())

    def test_generate_certificate(self):
        self._issuer.organizationName = "MAAS"
        self._issuer.organizationalUnitName = self.maas_uuid

        self.assertTrue(certificate_generated_by_this_maas(self._cert))

    def test_non_maas_certificate_no_o_ou(self):
        self.assertFalse(certificate_generated_by_this_maas(self._cert))

    def test_non_maas_certificate_with_o_ou(self):
        self._issuer.organizationName = "MAAS"
        self._issuer.organizationalUnitName = "not-this-maas"

        self.assertFalse(certificate_generated_by_this_maas(self._cert))


class TestGetSLLCertificate(MAASServerTestCase):
    def setUp(self):
        super().setUp()

    def test_get_certificate_http(self):
        (cert, fingerprint) = get_ssl_certificate("http://not.a.site")
        self.assertIsNone(cert)
        self.assertEqual("", fingerprint)

    def test_get_certificate(self):
        # fingerprint will eventually change due to certs changing
        (cert, _) = get_ssl_certificate("https://launchpad.net")
        self.assertEqual("launchpad.net", cert.get_subject().CN)
        self.assertEqual(
            "R3",
            cert.get_issuer().CN,
        )
        self.assertEqual("Let's Encrypt", cert.get_issuer().O)
