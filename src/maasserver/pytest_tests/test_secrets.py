import pytest

from maasserver.models import Secret
from maasserver.secrets import SecretManager, SecretNotFound
from maasserver.testing.factory import factory
from provisioningserver.utils.env import MAAS_ID, MAAS_UUID


@pytest.mark.django_db
@pytest.mark.usefixtures("vault_regionconfig")
class TestSecretManagerFromDB:
    def test_get_composite_secret_with_model(self):
        credentials = {"key": "ABC", "cert": "XYZ"}
        bmc = factory.make_BMC()
        Secret.objects.create(
            path=f"bmc/{bmc.id}/credentials",
            value=credentials,
        )
        manager = SecretManager()
        assert (
            manager.get_composite_secret("credentials", obj=bmc) == credentials
        )

    def test_get_composite_secret_with_model_not_found(self):
        bmc = factory.make_BMC()
        manager = SecretManager()
        with pytest.raises(SecretNotFound):
            manager.get_composite_secret("credentials", obj=bmc)

    def test_get_composite_secret_global(self):
        Secret.objects.create(path="global/foo", value={"bar": "baz"})
        manager = SecretManager()
        assert manager.get_composite_secret("foo") == {"bar": "baz"}

    def test_get_composite_secret_global_not_found(self):
        manager = SecretManager()
        with pytest.raises(SecretNotFound):
            manager.get_composite_secret("foo")

    def test_get_simple_with_model(self):
        metadata = factory.make_NodeMetadata()
        Secret.objects.create(
            path=f"nodemetadata/{metadata.id}/value", value={"secret": "foo"}
        )
        manager = SecretManager()
        assert manager.get_simple_secret("value", obj=metadata) == "foo"

    def test_get_simple_secret_global(self):
        Secret.objects.create(path="global/foo", value={"secret": "bar"})
        manager = SecretManager()
        assert manager.get_simple_secret("foo") == "bar"


@pytest.fixture
def configured_vault(factory, vault_regionconfig, mock_hvac_client):
    MAAS_ID.set(factory.make_name("id"))
    MAAS_UUID.set(factory.make_name("uuid"))
    vault_regionconfig["vault_url"] = "http://vault:8200"
    vault_regionconfig["vault_approle_id"] = factory.make_name("approle_id")
    vault_regionconfig["vault_secret_id"] = factory.make_name("secret_id")


@pytest.mark.django_db
@pytest.mark.usefixtures("configured_vault")
class TestSecretManagerFromVault:
    def test_get_composite_secret_with_model(self, mock_vault_kv):
        credentials = {"key": "ABC", "cert": "XYZ"}
        bmc = factory.make_BMC()
        mock_vault_kv.store[
            f"maas-{MAAS_UUID.get()}/bmc/{bmc.id}/credentials"
        ] = credentials
        manager = SecretManager()
        assert (
            manager.get_composite_secret("credentials", obj=bmc) == credentials
        )

    def test_get_composite_secret_with_model_not_found(self):
        bmc = factory.make_BMC()
        manager = SecretManager()
        with pytest.raises(SecretNotFound):
            manager.get_composite_secret("credentials", obj=bmc)

    def test_get_composite_secret_global(self, mock_vault_kv):
        mock_vault_kv.store[f"maas-{MAAS_UUID.get()}/global/foo"] = {
            "bar": "baz"
        }
        manager = SecretManager()
        assert manager.get_composite_secret("foo") == {"bar": "baz"}

    def test_get_composite_secret_global_not_found(self):
        manager = SecretManager()
        with pytest.raises(SecretNotFound):
            manager.get_composite_secret("foo")

    def test_get_simple_with_model(self, mock_vault_kv):
        metadata = factory.make_NodeMetadata()
        mock_vault_kv.store[
            f"maas-{MAAS_UUID.get()}/nodemetadata/{metadata.id}/value"
        ] = {"secret": "foo"}
        manager = SecretManager()
        assert manager.get_simple_secret("value", obj=metadata) == "foo"

    def test_get_simple_secret_global(self, mock_vault_kv):
        mock_vault_kv.store[f"maas-{MAAS_UUID.get()}/global/foo"] = {
            "secret": "bar"
        }
        manager = SecretManager()
        assert manager.get_simple_secret("foo") == "bar"
