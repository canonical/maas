# Copyright 2016-2019 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""The config handler for the WebSocket connection."""


from django.core.exceptions import ValidationError
from django.http import HttpRequest

from maasserver.enum import ENDPOINT
from maasserver.forms import ConfigForm
from maasserver.forms.settings import (
    CONFIG_ITEMS,
    CONFIG_ITEMS_KEYS,
    get_config_field,
    get_config_form,
)
from maasserver.models.config import Config
from maasserver.websockets.base import (
    Handler,
    HandlerDoesNotExistError,
    HandlerPermissionError,
    HandlerPKError,
    HandlerValidationError,
)


def get_config_keys(user):
    config_keys = list(CONFIG_ITEMS) + ["uuid", "maas_url"]
    if user.is_superuser:
        config_keys.append("rpc_shared_secret")
    return config_keys


class ConfigHandler(Handler):
    class Meta:
        pk = "name"
        allowed_methods = ["list", "get", "update", "bulk_update"]
        listen_channels = ["config"]

    def _include_choice(self, config_key):
        try:
            config_field = get_config_field(config_key["name"])
            if hasattr(config_field, "choices"):
                config_key["choices"] = config_field.choices
        except ValidationError:
            pass
        return config_key

    def _include_choices(self, config_keys):
        for config_key in config_keys:
            self._include_choice(config_key)
        return config_keys

    def dehydrate_configs(self, config_keys):
        return self._include_choices(
            [
                {"name": name, "value": value}
                for name, value in Config.objects.get_configs(
                    config_keys
                ).items()
            ]
        )

    def list(self, params):
        """List all the configuration values."""
        config_keys = get_config_keys(self.user)
        self.cache["loaded_pks"].update(config_keys)
        return self.dehydrate_configs(config_keys)

    def get(self, params):
        """Get a config value."""
        if "name" not in params:
            raise HandlerPKError("Missing name in params")
        name = params["name"]
        if name not in get_config_keys(self.user):
            raise HandlerDoesNotExistError(
                f"Configuration parameter ({name}) does not exist"
            )
        self.cache["loaded_pks"].update({name})
        return self.dehydrate_configs([name])[0]

    def _fix_validation_error(self, name, errors):
        """Map the field name to the value field, which is what is used
        over the websocket."""
        if name in errors:
            errors["value"] = errors.pop(name)

    def bulk_update(self, params):
        """Update config values in bulk."""
        if not self.user.is_superuser:
            raise HandlerPermissionError()
        if "items" not in params:
            raise HandlerPKError("Missing map of items in params")
        items = dict(params["items"])
        invalid_items = set(items.keys()) - CONFIG_ITEMS_KEYS
        if invalid_items:
            raise HandlerValidationError(
                {
                    name: ["Configuration parameter does not exist."]
                    for name in invalid_items
                }
            )

        form = ConfigForm(items)
        for name in items:
            form.fields[name] = get_config_field(name)

        if form.is_valid():
            try:
                request = HttpRequest()
                request.user = self.user
                form.save(ENDPOINT.UI, request)
            except ValidationError as e:
                raise HandlerValidationError(e.error_dict)
            else:
                return items
        else:
            raise HandlerValidationError(form.errors)

    def update(self, params):
        """Update a config value."""
        if not self.user.is_superuser:
            raise HandlerPermissionError()
        if "name" not in params:
            raise HandlerPKError("Missing name in params")
        if "value" not in params:
            raise HandlerValidationError("Missing value in params")
        name = params["name"]
        value = params["value"]
        try:
            form = get_config_form(name, {name: value})
        except ValidationError:
            raise HandlerDoesNotExistError(
                f"Configuration parameter ({name}) does not exist"
            )
        if form.is_valid():
            try:
                request = HttpRequest()
                request.user = self.user
                form.save(ENDPOINT.UI, request)
            except ValidationError as e:
                self._fix_validation_error(name, e.error_dict)
                raise HandlerValidationError(e.error_dict)
            return self._include_choice(
                {"name": name, "value": Config.objects.get_config(name)}
            )
        else:
            self._fix_validation_error(name, form.errors)
            raise HandlerValidationError(form.errors)

    def on_listen(self, channel, action, pk):
        """Override on_listen to always send the config values."""
        name = pk
        if name not in get_config_keys(self.user):
            return None
        action = "update" if name in self.cache["loaded_pks"] else "create"

        value = Config.objects.get_config(name=pk)
        return (
            self._meta.handler_name,
            action,
            self._include_choice({"name": name, "value": value}),
        )
