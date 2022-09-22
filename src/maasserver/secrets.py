from typing import Optional

from django.db.models import Model
from hvac.exceptions import InvalidPath

from maasserver.models import BMC, Config, NodeMetadata, RootKey, Secret
from maasserver.vault import get_region_vault_client

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

    def get_composite_secret(self, name: str, obj: Optional[Model] = None):
        """Return the value for a secret.

        The secret can be either global or for a model instance.
        """
        if obj:
            model_prefix = MODEL_SECRET_PREFIXES[type(obj)]
            prefix = f"{model_prefix}/{obj.id}"
        else:
            prefix = "global"

        path = f"{prefix}/{name}"
        if self._vault_client:
            return self._get_secret_from_vault(path)

        return self._get_secret_from_db(path)

    def get_simple_secret(self, name: str, obj: Optional[Model] = None):
        """Return the value for a simple secret.

        Simple secrets are stored as values of a single SIMPLE_SECRET_KEY key.

        The secret can be either global or for a model instance.
        """
        return self.get_composite_secret(name, obj=obj)[SIMPLE_SECRET_KEY]

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

    @property
    def _vault_client(self):
        return get_region_vault_client()
