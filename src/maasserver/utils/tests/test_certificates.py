from datetime import datetime, timedelta
from uuid import uuid1

from OpenSSL import crypto

from maasserver.models import Config
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.utils.certificates import (
    generate_certificate,
    get_maas_client_cn,
)


class TestGetMAASClientCN(MAASServerTestCase):
    def test_with_object(self):
        Config.objects.set_config("maas_name", "my-maas")
        object_name = "my-object"
        self.assertEqual("my-object@my-maas", get_maas_client_cn(object_name))

    def test_no_object(self):
        Config.objects.set_config("maas_name", "my-maas")
        self.assertEqual("my-maas", get_maas_client_cn(None))


class TestGenerateCertificate(MAASServerTestCase):
    def setUp(self):
        super().setUp()
        Config.objects.set_config("uuid", str(uuid1()))

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
        myuuid = str(uuid1())
        Config.objects.set_config("uuid", myuuid)
        cert = generate_certificate("maas")
        issuer = cert.cert.get_issuer()
        self.assertEqual("MAAS", issuer.O)
        self.assertEqual(myuuid, issuer.OU)
