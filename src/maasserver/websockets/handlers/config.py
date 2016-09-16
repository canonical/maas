# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""The config handler for the WebSocket connection."""

__all__ = [
    "ConfigHandler",
    ]

from django.core.exceptions import ValidationError
from maasserver.forms_settings import (
    CONFIG_ITEMS,
    get_config_form,
)
from maasserver.models.config import (
    Config,
    get_default_config,
)
from maasserver.websockets.base import (
    Handler,
    HandlerDoesNotExistError,
    HandlerPKError,
    HandlerValidationError,
)


class ConfigHandler(Handler):

    class Meta:
        allowed_methods = ['list', 'get', 'update']
        listen_channels = [
            "config",
            ]

    def list(self, params):
        """List all the configuration values."""
        defaults = get_default_config()
        config_keys = CONFIG_ITEMS.keys()
        config_objs = Config.objects.filter(name__in=config_keys)
        config_objs = {
            obj.name: obj
            for obj in config_objs
        }
        self.cache["loaded_pks"].update(config_keys)
        return [
            {
                'name': key,
                'value': (
                    config_objs[key].value
                    if key in config_objs else defaults.get(key, ''))
            }
            for key in config_keys
        ]

    def get(self, params):
        """Get a config value."""
        if 'name' not in params:
            raise HandlerPKError("Missing name in params")
        name = params['name']
        if name not in CONFIG_ITEMS:
            raise HandlerDoesNotExistError(name)
        self.cache["loaded_pks"].update({name, })
        return {
            'name': name,
            'value': Config.objects.get_config(name),
        }

    def _fix_validation_error(self, name, errors):
        """Map the field name to the value field, which is what is used
        over the websocket."""
        if name in errors:
            errors['value'] = errors.pop(name)

    def update(self, params):
        """Update a config value."""
        assert self.user.is_superuser, "Permission denied."
        if 'name' not in params:
            raise HandlerPKError("Missing name in params")
        if 'value' not in params:
            raise HandlerValidationError("Missing value in params")
        name = params['name']
        value = params['value']
        form = get_config_form(name, {name: value})
        if form.is_valid():
            try:
                form.save()
            except ValidationError as e:
                self._fix_validation_error(name, e.error_dict)
                raise HandlerValidationError(e.error_dict)
            return {
                'name': name,
                'value': Config.objects.get_config(name),
            }
        else:
            self._fix_validation_error(name, form.errors)
            raise HandlerValidationError(form.errors)

    def on_listen(self, channel, action, pk):
        """Override on_listen to always send the config values."""
        config = Config.objects.get(id=pk)
        if config.name not in CONFIG_ITEMS:
            return None
        if config.name in self.cache['loaded_pks']:
            action = "update"
        else:
            action = "create"
        return (self._meta.handler_name, action, {
            'name': config.name,
            'value': config.value,
        })
