from maasserver.models import Config
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.utils.certificates import get_maas_client_cn


class TestGetMAASClientCN(MAASServerTestCase):
    def test_with_object(self):
        Config.objects.set_config("maas_name", "my-maas")
        object_name = "my-object"
        self.assertEqual("my-object@my-maas", get_maas_client_cn(object_name))

    def test_no_object(self):
        Config.objects.set_config("maas_name", "my-maas")
        self.assertEqual("my-maas", get_maas_client_cn(None))
