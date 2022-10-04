from uuid import uuid4

from OpenSSL import crypto

from maasserver.models import Config
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
import maasserver.utils.certificates as certificates
from maasserver.utils.certificates import (
    certificate_generated_by_this_maas,
    generate_certificate,
    get_maas_client_cn,
)
from provisioningserver.certificates import Certificate
from provisioningserver.utils.env import MAAS_UUID


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
        maas_uuid = MAAS_UUID.get()
        if maas_uuid is None:
            MAAS_UUID.set(str(uuid4()))
        generate_certificate("maas")
        mock_cert.generate.assert_called_once_with(
            "maas",
            organization_name="MAAS",
            organizational_unit_name=MAAS_UUID.get(),
        )


class TestCertificateGeneratedByThisMAAS(MAASServerTestCase):
    def setUp(self):
        super().setUp()
        if MAAS_UUID.get() is None:
            MAAS_UUID.set(str(uuid4()))
        ssl_cert = crypto.X509()
        self._issuer = ssl_cert.get_issuer()
        self._cert = Certificate(None, ssl_cert, ())

    def test_generate_certificate(self):
        self._issuer.organizationName = "MAAS"
        self._issuer.organizationalUnitName = MAAS_UUID.get()

        self.assertTrue(certificate_generated_by_this_maas(self._cert))

    def test_non_maas_certificate_no_o_ou(self):
        self.assertFalse(certificate_generated_by_this_maas(self._cert))

    def test_non_maas_certificate_with_o_ou(self):
        self._issuer.organizationName = "MAAS"
        self._issuer.organizationalUnitName = "not-this-maas"

        self.assertFalse(certificate_generated_by_this_maas(self._cert))
