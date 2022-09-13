from typing import Optional

from django.db.models import Model

from maasserver.models import BMC, Config, NodeMetadata, RootKey, Secret

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

        secret = self._get_secret_from_db(f"{prefix}/{name}")
        return secret.value

    def get_simple_secret(self, name: str, obj: Optional[Model] = None):
        """Return the value for a simple secret.

        Simple secrets are stored as values of a single SIMPLE_SECRET_KEY key.

        The secret can be either global or for a model instance.
        """
        return self.get_composite_secret(name, obj=obj)[SIMPLE_SECRET_KEY]

    def _get_secret_from_db(self, path: str) -> Secret:
        try:
            return Secret.objects.get(path=path)
        except Secret.DoesNotExist:
            raise SecretNotFound(path)
