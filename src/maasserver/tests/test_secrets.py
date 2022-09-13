from maasserver.models import Secret
from maasserver.secrets import SecretManager, SecretNotFound
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase


class TestTest(MAASServerTestCase):
    def test_get_composite_secret_with_model(self):
        credentials = {"key": "ABC", "cert": "XYZ"}
        bmc = factory.make_BMC()
        Secret.objects.create(
            path=f"bmc/{bmc.id}/credentials",
            value=credentials,
        )
        manager = SecretManager()
        self.assertEqual(
            manager.get_composite_secret("credentials", obj=bmc),
            credentials,
        )

    def test_get_composite_secret_with_model_not_found(self):
        bmc = factory.make_BMC()
        manager = SecretManager()
        self.assertRaises(
            SecretNotFound,
            manager.get_composite_secret,
            "credentials",
            obj=bmc,
        )

    def test_get_composite_secret_global(self):
        Secret.objects.create(path="global/foo", value={"bar": "baz"})
        manager = SecretManager()
        self.assertEqual(manager.get_composite_secret("foo"), {"bar": "baz"})

    def test_get_composite_secret_global_not_found(self):
        manager = SecretManager()
        self.assertRaises(
            SecretNotFound,
            manager.get_composite_secret,
            "foo",
        )

    def test_get_simple_with_model(self):
        metadata = factory.make_NodeMetadata()
        Secret.objects.create(
            path=f"nodemetadata/{metadata.id}/value", value={"secret": "foo"}
        )
        manager = SecretManager()
        self.assertEqual(
            manager.get_simple_secret("value", obj=metadata),
            "foo",
        )

    def test_get_simple_secret_global(self):
        Secret.objects.create(path="global/foo", value={"secret": "bar"})
        manager = SecretManager()
        self.assertEqual(manager.get_simple_secret("foo"), "bar")
