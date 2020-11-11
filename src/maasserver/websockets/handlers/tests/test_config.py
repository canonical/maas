# Copyright 2016-2019 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `maasserver.websockets.handlers.config`"""


import random

from django.core.exceptions import ValidationError
from testtools import ExpectedException

from maasserver.forms.settings import get_config_field
from maasserver.models.config import Config, get_default_config
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.websockets.base import (
    HandlerDoesNotExistError,
    HandlerPermissionError,
    HandlerPKError,
    HandlerValidationError,
)
from maasserver.websockets.handlers.config import CONFIG_ITEMS, ConfigHandler


class TestConfigHandler(MAASServerTestCase):
    def dehydrated_all_configs(self):
        defaults = get_default_config()
        config_keys = CONFIG_ITEMS.keys()
        config_objs = Config.objects.filter(name__in=config_keys)
        config_objs = {obj.name: obj for obj in config_objs}
        config_keys = [
            {
                "name": key,
                "value": (
                    config_objs[key].value
                    if key in config_objs
                    else defaults.get(key, "")
                ),
            }
            for key in config_keys
        ]
        for config_key in config_keys:
            try:
                config_field = get_config_field(config_key["name"])
                if hasattr(config_field, "choices"):
                    config_key["choices"] = config_field.choices
            except ValidationError:
                pass
        return config_keys

    def test_get(self):
        user = factory.make_User()
        handler = ConfigHandler(user, {}, None)
        Config.objects.set_config("curtin_verbose", True)
        self.assertEquals(
            {"name": "curtin_verbose", "value": True},
            handler.get({"name": "curtin_verbose"}),
        )

    def test_get_sets_loaded_pks_in_cache(self):
        user = factory.make_User()
        handler = ConfigHandler(user, {}, None)
        Config.objects.set_config("curtin_verbose", True)
        handler.get({"name": "curtin_verbose"})
        self.assertEquals({"curtin_verbose"}, handler.cache["loaded_pks"])

    def test_get_requires_name(self):
        user = factory.make_User()
        handler = ConfigHandler(user, {}, None)
        self.assertRaises(HandlerPKError, handler.get, {})

    def test_get_must_be_known_config(self):
        user = factory.make_User()
        handler = ConfigHandler(user, {}, None)
        self.assertRaises(
            HandlerDoesNotExistError,
            handler.get,
            {"name": factory.make_name("config")},
        )

    def test_get_must_be_in_config_items(self):
        allowed_keys = set(CONFIG_ITEMS.keys())
        all_keys = set(get_default_config().keys())
        not_allowed_keys = all_keys.difference(allowed_keys)
        key = random.choice(list(not_allowed_keys))
        user = factory.make_User()
        handler = ConfigHandler(user, {}, None)
        self.assertRaises(HandlerDoesNotExistError, handler.get, {"name": key})

    def test_list(self):
        user = factory.make_User()
        handler = ConfigHandler(user, {}, None)
        self.assertItemsEqual(self.dehydrated_all_configs(), handler.list({}))

    def test_list_sets_loaded_pks_in_cache(self):
        user = factory.make_User()
        handler = ConfigHandler(user, {}, None)
        handler.list({})
        config_keys = {obj["name"] for obj in self.dehydrated_all_configs()}
        self.assertItemsEqual(config_keys, handler.cache["loaded_pks"])

    def test_update_as_non_admin_asserts(self):
        user = factory.make_User()
        handler = ConfigHandler(user, {}, None)
        with ExpectedException(HandlerPermissionError):
            handler.update({})

    def test_update_requires_name(self):
        user = factory.make_admin()
        handler = ConfigHandler(user, {}, None)
        self.assertRaises(HandlerPKError, handler.update, {})

    def test_update_requires_value(self):
        user = factory.make_admin()
        handler = ConfigHandler(user, {}, None)
        self.assertRaises(
            HandlerValidationError, handler.update, {"name": "curtin_verbose"}
        )

    def test_update_updates_value(self):
        user = factory.make_admin()
        handler = ConfigHandler(user, {}, None)
        updated = handler.update({"name": "curtin_verbose", "value": True})
        self.assertEquals({"name": "curtin_verbose", "value": True}, updated)
        self.assertTrue(Config.objects.get_config("curtin_verbose"))

    def test_update_cannot_update_uuid(self):
        user = factory.make_admin()
        handler = ConfigHandler(user, {}, None)
        self.assertRaises(
            HandlerDoesNotExistError,
            handler.update,
            {"name": "uuid", "value": "uuid"},
        )

    def test_update_cannot_update_rpc_shared_secret(self):
        user = factory.make_admin()
        handler = ConfigHandler(user, {}, None)
        self.assertRaises(
            HandlerDoesNotExistError,
            handler.update,
            {"name": "rpc_shared_secret", "value": "rpc_shared_secret"},
        )

    def test_update_cannot_update_maas_url(self):
        user = factory.make_admin()
        handler = ConfigHandler(user, {}, None)
        self.assertRaises(
            HandlerDoesNotExistError,
            handler.update,
            {"name": "maas_url", "value": "maas_url"},
        )

    def test_update_handles_bad_value(self):
        user = factory.make_admin()
        handler = ConfigHandler(user, {}, None)
        error = self.assertRaises(
            HandlerValidationError,
            handler.update,
            {"name": "http_proxy", "value": factory.make_name("invalid")},
        )
        self.assertEquals(
            {"value": ["Enter a valid URL."]}, error.message_dict
        )

    def test_on_listen_returns_None_if_excluded(self):
        user = factory.make_User()
        handler = ConfigHandler(user, {}, None)
        Config.objects.set_config("omapi_key", "")
        obj = Config.objects.get(name="omapi_key")
        self.assertIsNone(handler.on_listen("config", "create", obj.id))

    def test_on_listen_returns_create_for_not_loaded(self):
        user = factory.make_User()
        handler = ConfigHandler(user, {}, None)
        Config.objects.set_config("curtin_verbose", True)
        obj = Config.objects.get(name="curtin_verbose")
        updated = handler.on_listen("config", "update", obj.id)
        self.assertEqual(
            ("config", "create", {"name": "curtin_verbose", "value": True}),
            updated,
        )

    def test_on_listen_returns_update_for_loaded_create(self):
        user = factory.make_User()
        handler = ConfigHandler(user, {}, None)
        handler.cache["loaded_pks"] = {"curtin_verbose"}
        Config.objects.set_config("curtin_verbose", True)
        obj = Config.objects.get(name="curtin_verbose")
        updated = handler.on_listen("config", "create", obj.id)
        self.assertEqual(
            ("config", "update", {"name": "curtin_verbose", "value": True}),
            updated,
        )

    def test_on_listen_returns_update_for_loaded_delete(self):
        user = factory.make_User()
        handler = ConfigHandler(user, {}, None)
        handler.cache["loaded_pks"] = {"curtin_verbose"}
        Config.objects.set_config("curtin_verbose", True)
        obj = Config.objects.get(name="curtin_verbose")
        updated = handler.on_listen("config", "delete", obj.id)
        self.assertEqual(
            ("config", "update", {"name": "curtin_verbose", "value": True}),
            updated,
        )
