from typing import Any, Optional

from django.db.models import Model
from hvac.exceptions import InvalidPath

from maasserver.models import BMC, Config, NodeMetadata, RootKey, Secret
from maasserver.vault import get_region_vault_client, VaultClient

SIMPLE_SECRET_KEY = "secret"


MODEL_SECRET_PREFIXES = {
    BMC: "bmc",
    Config: "config",
    RootKey: "rootkey",
    NodeMetadata: "nodemetadata",
}


class SecretNotFound(Exception):
    """Raised when a secret is not found."""

    def __init__(self, path: str):
        self.path = path
        super().__init__(f"Secret '{path}' not found")


class SecretManager:
    """Handle operations on secrets."""

    def __init__(self, vault_client: Optional[VaultClient] = None):
        self._vault_client = vault_client or get_region_vault_client()

    def set_composite_secret(
        self, name: str, value: dict[str, Any], obj: Optional[Model] = None
    ):
        """Create or update a secret."""
        path = self._get_secret_path(name, obj=obj)
        if self._vault_client:
            self._vault_client.set(path, value)

        Secret.objects.update_or_create(path=path, defaults={"value": value})

    def set_simple_secret(
        self, name: str, value: Any, obj: Optional[Model] = None
    ):
        """Create or update a simple secret."""
        self.set_composite_secret(
            name, value={SIMPLE_SECRET_KEY: value}, obj=obj
        )

    def delete_secret(self, name: str, obj: Optional[Model] = None):
        """Delete a secret, either global or for a model instance."""
        path = self._get_secret_path(name, obj=obj)
        if self._vault_client:
            self._vault_client.delete(path)

        Secret.objects.filter(path=path).delete()

    def get_composite_secret(self, name: str, obj: Optional[Model] = None):
        """Return the value for a secret.

        The secret can be either global or for a model instance.
        """
        path = self._get_secret_path(name, obj=obj)
        if self._vault_client:
            return self._get_secret_from_vault(path)

        return self._get_secret_from_db(path)

    def get_simple_secret(self, name: str, obj: Optional[Model] = None):
        """Return the value for a simple secret.

        Simple secrets are stored as values of a single SIMPLE_SECRET_KEY key.

        The secret can be either global or for a model instance.
        """
        return self.get_composite_secret(name, obj=obj)[SIMPLE_SECRET_KEY]

    def _get_secret_path(self, name: str, obj: Optional[Model] = None):
        if obj:
            model_prefix = MODEL_SECRET_PREFIXES[type(obj)]
            prefix = f"{model_prefix}/{obj.id}"
        else:
            prefix = "global"

        return f"{prefix}/{name}"

    def _get_secret_from_db(self, path: str):
        try:
            return Secret.objects.get(path=path).value
        except Secret.DoesNotExist:
            raise SecretNotFound(path)

    def _get_secret_from_vault(self, path: str):
        try:
            return self._vault_client.get(path)
        except InvalidPath:
            raise SecretNotFound(path)
