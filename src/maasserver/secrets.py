from typing import Any, Literal, NamedTuple, Optional

from django.db.models import Model

from maasserver.models import BMC, Node, RootKey, Secret, VaultSecret
from maasserver.vault import (
    get_region_vault_client_if_enabled,
    UnknownSecretPath,
    VaultClient,
)

SIMPLE_SECRET_KEY = "secret"


class UnknownSecret(Exception):
    """Path for an unknown secret has been requested."""

    def __init__(self, name: str, obj: Optional[Model] = None):
        self.name = name
        self.obj = obj
        message = f"Unknown secret '{name}'"
        if obj is not None:
            message += f" for object {type(obj)}"
        super().__init__(message)


class SecretNotFound(Exception):
    """Raised when a secret is not found."""

    def __init__(self, path: str):
        self.path = path
        super().__init__(f"Secret '{path}' not found")


class ModelSecret(NamedTuple):
    model: Model
    prefix: str
    secret_names: list[str]

    def get_secret_path(self, name: str, obj: Model) -> str:
        if name not in self.secret_names:
            raise UnknownSecret(name, obj=obj)
        return f"{self.prefix}/{obj.id}/{name}"


MODEL_SECRETS = {
    secret.model: secret
    for secret in (
        ModelSecret(Node, "node", ["deploy-metadata", "power-parameters"]),
        ModelSecret(RootKey, "rootkey", ["material"]),
        ModelSecret(BMC, "bmc", ["power-parameters"]),
    )
}

GLOBAL_SECRETS = frozenset(
    [
        "external-auth",
        "ipmi-k_g-key",
        "macaroon-key",
        "omapi-key",
        "rpc-shared",
        "cluster-certificate",
        "tls",
        "vcenter-password",
    ]
)

UNSET = object()


class SecretManager:
    """Handle operations on secrets."""

    def __init__(
        self, vault_client: VaultClient | None | Literal[UNSET] = UNSET
    ):
        if vault_client is not UNSET:
            self._vault_client = vault_client
        else:
            self._vault_client = get_region_vault_client_if_enabled()

    def set_composite_secret(
        self, name: str, value: dict[str, Any], obj: Optional[Model] = None
    ):
        """Create or update a secret."""
        path = self._get_secret_path(name, obj=obj)
        if self._vault_client:
            self._vault_client.set(path, value)
            VaultSecret.objects.update_or_create(
                path=path, defaults={"deleted": False}
            )
        else:
            Secret.objects.update_or_create(
                path=path, defaults={"value": value}
            )

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
            VaultSecret.objects.filter(path=path).update(deleted=True)
        else:
            Secret.objects.filter(path=path).delete()

    def delete_all_object_secrets(self, obj: Model):
        """Delete all known secrets for an object."""
        model_secret = MODEL_SECRETS[type(obj)]
        paths = tuple(
            model_secret.get_secret_path(name, obj)
            for name in model_secret.secret_names
        )
        if self._vault_client:
            VaultSecret.objects.filter(path__in=paths).update(deleted=True)
        else:
            Secret.objects.filter(path__in=paths).delete()

    def get_composite_secret(
        self,
        name: str,
        obj: Optional[Model] = None,
        default: Any = UNSET,
    ):
        """Return the value for a secret.

        The secret can be either global or for a model instance.
        """
        path = self._get_secret_path(name, obj=obj)
        try:
            if self._vault_client:
                vault_secret = VaultSecret.objects.filter(path=path).first()
                if not vault_secret or vault_secret.deleted:
                    raise SecretNotFound(path)
                return self._get_secret_from_vault(path)

            return self._get_secret_from_db(path)
        except SecretNotFound:
            if default is UNSET:
                raise
            return default

    def get_simple_secret(
        self,
        name: str,
        obj: Optional[Model] = None,
        default: Any = UNSET,
    ):
        """Return the value for a simple secret.

        Simple secrets are stored as values of a single SIMPLE_SECRET_KEY key.

        The secret can be either global or for a model instance.
        """
        try:
            secret = self.get_composite_secret(name, obj=obj)
        except SecretNotFound:
            if default is UNSET:
                raise
            return default
        return secret[SIMPLE_SECRET_KEY]

    def _get_secret_path(self, name: str, obj: Optional[Model] = None) -> str:
        if obj is not None:
            try:
                model_secret = MODEL_SECRETS[type(obj)]
            except KeyError:
                raise UnknownSecret(name, obj=obj)
            return model_secret.get_secret_path(name, obj)

        if name not in GLOBAL_SECRETS:
            raise UnknownSecret(name)
        return f"global/{name}"

    def _get_secret_from_db(self, path: str):
        try:
            return Secret.objects.get(path=path).value
        except Secret.DoesNotExist:
            raise SecretNotFound(path)

    def _get_secret_from_vault(self, path: str):
        try:
            return self._vault_client.get(path)
        except UnknownSecretPath:
            raise SecretNotFound(path)
