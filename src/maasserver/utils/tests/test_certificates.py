from uuid import uuid4

from OpenSSL import crypto

from maasserver.models import Config
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
import maasserver.utils.certificates as certificates
from maasserver.utils.certificates import (
    certificate_generated_by_this_maas,
    generate_certificate,
    generate_self_signed_v3_certificate,
    get_maas_client_cn,
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


class TestGenerateSelfSignedCertificate(MAASServerTestCase):
    def test_generate_self_signed_certificate(self):
        mock_cert = self.patch_autospec(certificates, "Certificate")
        maas_uuid = str(uuid4())
        self.useFixture(MAASUUIDFixture(maas_uuid))
        generate_self_signed_v3_certificate("maas", b"DNS:*")
        mock_cert.generate_self_signed_v3.assert_called_once_with(
            "maas",
            organization_name="MAAS",
            organizational_unit_name=maas_uuid,
            subject_alternative_name=b"DNS:*",
        )


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
