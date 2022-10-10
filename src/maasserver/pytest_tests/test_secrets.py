import pytest

from maasserver.models import Secret
from maasserver.secrets import SecretManager, SecretNotFound
from maasserver.testing.factory import factory
from provisioningserver.utils.env import MAAS_ID, MAAS_UUID


@pytest.mark.django_db
class TestSecretManagerFromDB:
    def test_get_composite_secret_with_model(self):
        data = {"key": "ABC", "cert": "XYZ"}
        node = factory.make_Node()
        Secret.objects.create(
            path=f"node/{node.id}/foo",
            value=data,
        )
        manager = SecretManager()
        assert manager.get_composite_secret("foo", obj=node) == data

    def test_get_composite_secret_with_model_not_found(self):
        node = factory.make_Node()
        manager = SecretManager()
        with pytest.raises(SecretNotFound):
            manager.get_composite_secret("foo", obj=node)

    def test_get_composite_secret_with_model_not_found_default(self):
        node = factory.make_Node()
        manager = SecretManager()
        assert (
            manager.get_composite_secret("foo", obj=node, default="default")
            == "default"
        )

    def test_get_composite_secret_global(self):
        Secret.objects.create(path="global/foo", value={"bar": "baz"})
        manager = SecretManager()
        assert manager.get_composite_secret("foo") == {"bar": "baz"}

    def test_get_composite_secret_global_not_found(self):
        manager = SecretManager()
        with pytest.raises(SecretNotFound):
            manager.get_composite_secret("foo")

    def test_get_composite_secret_global_not_found_default(self):
        manager = SecretManager()
        assert (
            manager.get_composite_secret("foo", default="default") == "default"
        )

    def test_get_simple_secret_with_model(self):
        node = factory.make_Node()
        Secret.objects.create(
            path=f"node/{node.id}/value", value={"secret": "foo"}
        )
        manager = SecretManager()
        assert manager.get_simple_secret("value", obj=node) == "foo"

    def test_get_simple_secret_with_model_not_found(self):
        node = factory.make_Node()
        manager = SecretManager()
        with pytest.raises(SecretNotFound):
            manager.get_simple_secret("value", obj=node)

    def test_get_simple_secret_with_model_not_found_default(self):
        node = factory.make_Node()
        manager = SecretManager()
        assert (
            manager.get_simple_secret("value", obj=node, default="bar")
            == "bar"
        )

    def test_get_simple_secret_global(self):
        Secret.objects.create(path="global/foo", value={"secret": "bar"})
        manager = SecretManager()
        assert manager.get_simple_secret("foo") == "bar"

    def get_simple_secret_global_not_found(self):
        manager = SecretManager()
        with pytest.raises(SecretNotFound):
            manager.get_simple_secret("foo")

    def get_simple_secret_global_not_found_default(self):
        manager = SecretManager()
        assert manager.get_simple_secret("foo", default="bar") == "bar"

    def test_set_composite_secret_with_model(self):
        node = factory.make_Node()
        manager = SecretManager()
        value = {"bar": "baz"}
        manager.set_composite_secret("foo", value, obj=node)
        assert Secret.objects.get(path=f"node/{node.id}/foo").value == value

    def test_set_composite_secret_global(self):
        manager = SecretManager()
        value = {"bar": "baz"}
        manager.set_composite_secret("foo", value)
        assert Secret.objects.get(path="global/foo").value == value

    def test_set_simple_secret_with_model(self):
        node = factory.make_Node()
        manager = SecretManager()
        value = {"bar": "baz"}
        manager.set_simple_secret("foo", value, obj=node)
        assert Secret.objects.get(path=f"node/{node.id}/foo").value == {
            "secret": value
        }

    def test_set_simple_secret_global(self):
        manager = SecretManager()
        value = {"bar": "baz"}
        manager.set_simple_secret("foo", value)
        assert Secret.objects.get(path="global/foo").value == {"secret": value}

    def test_delete_secret_with_model(self):
        node = factory.make_Node()
        manager = SecretManager()
        manager.set_composite_secret("foo", {"bar": "baz"}, obj=node)
        manager.delete_secret("foo", obj=node)
        assert not Secret.objects.exists()

    def test_delete_secret_global(self):
        manager = SecretManager()
        manager.set_simple_secret("foo", {"bar": "baz"})
        manager.delete_secret("foo")
        assert not Secret.objects.exists()

    def test_delete_all_object_secrets_only_object(self):
        node1 = factory.make_Node()
        node2 = factory.make_Node()
        manager = SecretManager()
        value = {"foo": "bar"}
        manager.set_simple_secret("deploy-metadata", value, obj=node1)
        manager.set_simple_secret("deploy-metadata", value, obj=node2)
        manager.delete_all_object_secrets(node1)
        assert list(Secret.objects.values_list("path", flat=True)) == [
            f"node/{node2.id}/deploy-metadata"
        ]

    def test_delete_all_object_secrets_only_known(self):
        node = factory.make_Node()
        manager = SecretManager()
        manager.set_simple_secret("deploy-metadata", {"foo": "bar"}, obj=node)
        manager.set_simple_secret("unknown", {"baz": "bza"}, obj=node)
        manager.delete_all_object_secrets(node)
        assert list(Secret.objects.values_list("path", flat=True)) == [
            f"node/{node.id}/unknown"
        ]


@pytest.fixture
def configured_vault(factory, vault_regionconfig, mock_hvac_client):
    MAAS_ID.set(factory.make_name("id"))
    MAAS_UUID.set(factory.make_name("uuid"))
    vault_regionconfig["vault_url"] = "http://vault:8200"
    vault_regionconfig["vault_approle_id"] = factory.make_name("approle_id")
    vault_regionconfig["vault_secret_id"] = factory.make_name("secret_id")


class MockVaultClient:
    def __init__(self):
        self.store = {}

    def set(self, path, value):
        self.store[path] = value

    def get(self, path):
        try:
            return self.store[path]
        except KeyError:
            raise SecretNotFound(path)

    def delete(self, path):
        self.store.pop(path, None)


@pytest.fixture
def mock_vault_client():
    return MockVaultClient()


@pytest.mark.django_db
class TestSecretManagerFromVault:
    def test_get_composite_secret_with_model(self, mock_vault_client):
        data = {"key": "ABC", "cert": "XYZ"}
        node = factory.make_Node()
        mock_vault_client.store[f"node/{node.id}/foo"] = data
        manager = SecretManager(vault_client=mock_vault_client)
        assert manager.get_composite_secret("foo", obj=node) == data

    def test_get_composite_secret_with_model_not_found(
        self, mock_vault_client
    ):
        node = factory.make_Node()
        manager = SecretManager(vault_client=mock_vault_client)
        with pytest.raises(SecretNotFound):
            manager.get_composite_secret("foo", obj=node)

    def test_get_composite_secret_with_model_not_found_default(
        self, mock_vault_client
    ):
        node = factory.make_Node()
        manager = SecretManager(vault_client=mock_vault_client)
        assert (
            manager.get_composite_secret("foo", obj=node, default="default")
            == "default"
        )

    def test_get_composite_secret_global(self, mock_vault_client):
        mock_vault_client.store["global/foo"] = {"bar": "baz"}
        manager = SecretManager(vault_client=mock_vault_client)
        assert manager.get_composite_secret("foo") == {"bar": "baz"}

    def test_get_composite_secret_global_not_found(self, mock_vault_client):
        manager = SecretManager(vault_client=mock_vault_client)
        with pytest.raises(SecretNotFound):
            manager.get_composite_secret("foo")

    def test_get_composite_secret_global_not_found_default(
        self, mock_vault_client
    ):
        manager = SecretManager(vault_client=mock_vault_client)
        assert (
            manager.get_composite_secret("foo", default="default") == "default"
        )

    def test_get_simple_with_model(self, mock_vault_client):
        node = factory.make_Node()
        mock_vault_client.store[f"node/{node.id}/value"] = {"secret": "foo"}
        manager = SecretManager(vault_client=mock_vault_client)
        assert manager.get_simple_secret("value", obj=node) == "foo"

    def test_get_simple_secret_with_model_not_found(self, mock_vault_client):
        node = factory.make_Node()
        manager = SecretManager(vault_client=mock_vault_client)
        with pytest.raises(SecretNotFound):
            manager.get_simple_secret("value", obj=node)

    def test_get_simple_secret_with_model_not_found_default(
        self, mock_vault_client
    ):
        node = factory.make_Node()
        manager = SecretManager(vault_client=mock_vault_client)
        assert (
            manager.get_simple_secret("value", obj=node, default="bar")
            == "bar"
        )

    def test_get_simple_secret_global(self, mock_vault_client):
        mock_vault_client.store["global/foo"] = {"secret": "bar"}
        manager = SecretManager(vault_client=mock_vault_client)
        assert manager.get_simple_secret("foo") == "bar"

    def get_simple_secret_global_not_found(self, mock_vault_client):
        manager = SecretManager(vault_client=mock_vault_client)
        with pytest.raises(SecretNotFound):
            manager.get_simple_secret("foo")

    def get_simple_secret_global_not_found_default(self, mock_vault_client):
        manager = SecretManager(vault_client=mock_vault_client)
        assert manager.get_simple_secret("foo", default="bar") == "bar"

    def test_set_composite_secret_with_model(self, mock_vault_client):
        node = factory.make_Node()
        manager = SecretManager(vault_client=mock_vault_client)
        value = {"bar": "baz"}
        manager.set_composite_secret("foo", value, obj=node)
        assert mock_vault_client.store == {f"node/{node.id}/foo": value}

    def test_set_composite_secret_global(self, mock_vault_client):
        manager = SecretManager(vault_client=mock_vault_client)
        value = {"bar": "baz"}
        manager.set_composite_secret("foo", value)
        assert mock_vault_client.store == {"global/foo": value}

    def test_set_simple_secret_with_model(self, mock_vault_client):
        node = factory.make_Node()
        manager = SecretManager(vault_client=mock_vault_client)
        value = {"bar": "baz"}
        manager.set_simple_secret("foo", value, obj=node)
        assert mock_vault_client.store == {
            f"node/{node.id}/foo": {"secret": value}
        }

    def test_set_simple_secret_global(self, mock_vault_client):
        manager = SecretManager(vault_client=mock_vault_client)
        value = {"bar": "baz"}
        manager.set_simple_secret("foo", value)
        assert mock_vault_client.store == {"global/foo": {"secret": value}}

    def test_delete_secret_with_model(self, mock_vault_client):
        node = factory.make_Node()
        manager = SecretManager(vault_client=mock_vault_client)
        manager.set_composite_secret("foo", {"bar": "baz"}, obj=node)
        manager.delete_secret("foo", obj=node)
        assert mock_vault_client.store == {}

    def test_delete_secret_global(self, mock_vault_client):
        manager = SecretManager(vault_client=mock_vault_client)
        manager.set_simple_secret("foo", {"bar": "baz"})
        manager.delete_secret("foo")
        assert mock_vault_client.store == {}

    def test_delete_all_object_secrets_only_object(self, mock_vault_client):
        node1 = factory.make_Node()
        node2 = factory.make_Node()
        manager = SecretManager(vault_client=mock_vault_client)
        value = {"foo": "bar"}
        manager.set_simple_secret("deploy-metadata", value, obj=node1)
        manager.set_simple_secret("deploy-metadata", value, obj=node2)
        manager.delete_all_object_secrets(node1)
        assert mock_vault_client.store == {
            f"node/{node2.id}/deploy-metadata": {"secret": value}
        }

    def test_delete_all_object_secrets_only_known(self, mock_vault_client):
        node = factory.make_Node()
        manager = SecretManager(vault_client=mock_vault_client)
        manager.set_simple_secret("deploy-metadata", {"foo": "bar"}, obj=node)
        manager.set_simple_secret("unknown", {"baz": "bza"}, obj=node)
        manager.delete_all_object_secrets(node)
        assert mock_vault_client.store == {
            f"node/{node.id}/unknown": {"secret": {"baz": "bza"}}
        }
