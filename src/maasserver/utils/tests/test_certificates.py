from datetime import datetime, timedelta
from uuid import uuid1

from OpenSSL import crypto

from maasserver.models import Config
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
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
    def setUp(self):
        super().setUp()
        MAAS_UUID.set(str(uuid1()))

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

    def test_generate_certificate_issuer(self):
        cert = generate_certificate("maas")
        issuer = cert.cert.get_issuer()
        self.assertEqual("MAAS", issuer.O)
        self.assertEqual(MAAS_UUID.get(), issuer.OU)


class TestCertificateGeneratedByThisMAAS(MAASServerTestCase):
    def test_generate_certificate(self):
        maas_cert = generate_certificate("mycn")
        self.assertTrue(certificate_generated_by_this_maas(maas_cert))

    def test_non_maas_certificate_no_o_ou(self):
        non_maas_cert = Certificate.generate("mycn")
        self.assertFalse(certificate_generated_by_this_maas(non_maas_cert))

    def test_non_maas_certificate_with_o_ou(self):
        non_maas_cert = Certificate.generate(
            "mycn",
            organization_name="MAAS",
            organizational_unit_name="not-this-maas",
        )
        self.assertFalse(certificate_generated_by_this_maas(non_maas_cert))
