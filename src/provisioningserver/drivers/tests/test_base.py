# Copyright 2014-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `provisioningserver.drivers`."""

import random
import re
from unittest.mock import sentinel

from jsonschema import validate, ValidationError

from maastesting.factory import factory
from maastesting.testcase import MAASTestCase
from provisioningserver.drivers import (
    Architecture,
    ArchitectureRegistry,
    IP_EXTRACTOR_PATTERNS,
    make_setting_field,
    SETTING_PARAMETER_FIELD_SCHEMA,
    SETTING_SCOPE,
)
from provisioningserver.utils.testing import RegistryFixture


class TestIpExtractor(MAASTestCase):
    scenarios = (
        (
            "no-name",
            {
                "val": "http://:555/path",
                "expected": {
                    "password": None,
                    "port": "555",
                    "path": "/path",
                    "query": None,
                    "address": "",
                    "user": None,
                    "schema": "http",
                },
            },
        ),
        (
            "name-with-brackets",
            {"val": "http://[localhost]/path", "expected": None},
        ),
        (
            "ipv4-with-brackets",
            {"val": "http://[127.0.0.1]/path", "expected": None},
        ),
        (
            "ipv4-with-leading-bracket",
            {"val": "http://[127.0.0.1/path", "expected": None},
        ),
        (
            "ipv4-with-trailing-bracket",
            {"val": "http://127.0.0.1]/path", "expected": None},
        ),
        (
            "ipv6-no-brackets",
            {"val": "http://2001:db8::1/path", "expected": None},
        ),
        (
            "name",
            {
                "val": "http://localhost:555/path",
                "expected": {
                    "password": None,
                    "port": "555",
                    "path": "/path",
                    "query": None,
                    "address": "localhost",
                    "user": None,
                    "schema": "http",
                },
            },
        ),
        (
            "ipv4",
            {
                "val": "http://127.0.0.1:555/path",
                "expected": {
                    "password": None,
                    "port": "555",
                    "path": "/path",
                    "query": None,
                    "address": "127.0.0.1",
                    "user": None,
                    "schema": "http",
                },
            },
        ),
        (
            "ipv6-formatted-ipv4",
            {
                "val": "http://[::ffff:127.0.0.1]:555/path",
                "expected": {
                    "password": None,
                    "port": "555",
                    "path": "/path",
                    "query": None,
                    "address": "::ffff:127.0.0.1",
                    "user": None,
                    "schema": "http",
                },
            },
        ),
        (
            "ipv6",
            {
                "val": "http://[2001:db8::1]:555/path",
                "expected": {
                    "password": None,
                    "port": "555",
                    "path": "/path",
                    "query": None,
                    "address": "2001:db8::1",
                    "user": None,
                    "schema": "http",
                },
            },
        ),
        (
            "ipv4-no-slash",
            {
                "val": "http://127.0.0.1",
                "expected": {
                    "password": None,
                    "port": None,
                    "path": None,
                    "query": None,
                    "address": "127.0.0.1",
                    "user": None,
                    "schema": "http",
                },
            },
        ),
        (
            "name-no-slash",
            {
                "val": "http://localhost",
                "expected": {
                    "password": None,
                    "port": None,
                    "path": None,
                    "query": None,
                    "address": "localhost",
                    "user": None,
                    "schema": "http",
                },
            },
        ),
        (
            "ipv6-no-slash",
            {
                "val": "http://[2001:db8::1]",
                "expected": {
                    "password": None,
                    "port": None,
                    "path": None,
                    "query": None,
                    "address": "2001:db8::1",
                    "user": None,
                    "schema": "http",
                },
            },
        ),
        (
            "ipv4-no-port",
            {
                "val": "http://127.0.0.1/path",
                "expected": {
                    "password": None,
                    "port": None,
                    "path": "/path",
                    "query": None,
                    "address": "127.0.0.1",
                    "user": None,
                    "schema": "http",
                },
            },
        ),
        (
            "name-no-port",
            {
                "val": "http://localhost/path",
                "expected": {
                    "password": None,
                    "port": None,
                    "path": "/path",
                    "query": None,
                    "address": "localhost",
                    "user": None,
                    "schema": "http",
                },
            },
        ),
        (
            "ipv6-no-port",
            {
                "val": "http://[2001:db8::1]/path",
                "expected": {
                    "password": None,
                    "port": None,
                    "path": "/path",
                    "query": None,
                    "address": "2001:db8::1",
                    "user": None,
                    "schema": "http",
                },
            },
        ),
        (
            "user-pass-ipv4",
            {
                "val": "http://user:pass@127.0.0.1:555/path",
                "expected": {
                    "password": "pass",
                    "port": "555",
                    "path": "/path",
                    "query": None,
                    "address": "127.0.0.1",
                    "user": "user",
                    "schema": "http",
                },
            },
        ),
        (
            "user-pass-ipv6",
            {
                "val": "http://user:pass@[2001:db8::1]:555/path",
                "expected": {
                    "password": "pass",
                    "port": "555",
                    "path": "/path",
                    "query": None,
                    "address": "2001:db8::1",
                    "user": "user",
                    "schema": "http",
                },
            },
        ),
        (
            "user-pass-ipv4-no-port",
            {
                "val": "http://user:pass@127.0.0.1/path",
                "expected": {
                    "password": "pass",
                    "port": None,
                    "path": "/path",
                    "query": None,
                    "address": "127.0.0.1",
                    "user": "user",
                    "schema": "http",
                },
            },
        ),
        (
            "user-pass-ipv6-no-port",
            {
                "val": "http://user:pass@[2001:db8::1]/path",
                "expected": {
                    "password": "pass",
                    "port": None,
                    "path": "/path",
                    "query": None,
                    "address": "2001:db8::1",
                    "user": "user",
                    "schema": "http",
                },
            },
        ),
    )

    def test_make_ip_extractor(self):
        actual = re.match(IP_EXTRACTOR_PATTERNS.URL, self.val)
        if self.expected is None:
            self.assertIsNone(actual)
        else:
            self.assertEqual(actual.groupdict(), self.expected)


class TestMakeSettingField(MAASTestCase):
    def test_returns_valid_schema(self):
        setting = make_setting_field(
            factory.make_name("name"), factory.make_name("label")
        )
        # doesn't raise ValidationError
        validate(setting, SETTING_PARAMETER_FIELD_SCHEMA)

    def test_returns_dict_with_required_fields(self):
        setting = make_setting_field(
            factory.make_name("name"), factory.make_name("label")
        )
        self.assertLess(
            {
                "name",
                "label",
                "required",
                "field_type",
                "choices",
                "default",
                "scope",
            },
            setting.keys(),
        )

    def test_defaults_field_type_to_string(self):
        setting = make_setting_field(
            factory.make_name("name"), factory.make_name("label")
        )
        self.assertEqual("string", setting["field_type"])

    def test_defaults_choices_to_empty_list(self):
        setting = make_setting_field(
            factory.make_name("name"), factory.make_name("label")
        )
        self.assertEqual([], setting["choices"])

    def test_defaults_default_to_empty_string(self):
        setting = make_setting_field(
            factory.make_name("name"), factory.make_name("label")
        )
        self.assertEqual("", setting["default"])

    def test_validates_choices(self):
        choices = ["invalid"]
        self.assertRaises(
            ValidationError,
            make_setting_field,
            factory.make_name("name"),
            factory.make_name("label"),
            field_type="choice",
            choices=choices,
        )

    def test_returns_dict_with_correct_values(self):
        name = factory.make_name("name")
        label = factory.make_name("label")
        field_type = random.choice(["string", "mac_address", "choice"])
        choices = [
            [factory.make_name("key"), factory.make_name("value")]
            for _ in range(3)
        ]
        default = factory.make_name("default")
        setting = make_setting_field(
            name,
            label,
            field_type=field_type,
            choices=choices,
            default=default,
            required=True,
            scope=SETTING_SCOPE.NODE,
        )
        self.assertEqual(
            {
                "name": name,
                "label": label,
                "field_type": field_type,
                "choices": choices,
                "default": default,
                "required": True,
                "scope": SETTING_SCOPE.NODE,
                "secret": False,
            },
            setting,
        )


class TestRegistries(MAASTestCase):
    def setUp(self):
        super().setUp()
        # Ensure the global registry is empty for each test run.
        self.useFixture(RegistryFixture())

    def test_architecture_registry(self):
        self.assertEqual([], list(ArchitectureRegistry))
        ArchitectureRegistry.register_item("resource", sentinel.resource)
        self.assertIn(
            sentinel.resource, (item for name, item in ArchitectureRegistry)
        )

    def test_get_by_pxealias_returns_valid_arch(self):
        arch1 = Architecture(
            name="arch1",
            description="arch1",
            pxealiases=["archibald", "reginald"],
        )
        arch2 = Architecture(
            name="arch2", description="arch2", pxealiases=["fake", "foo"]
        )
        ArchitectureRegistry.register_item("arch1", arch1)
        ArchitectureRegistry.register_item("arch2", arch2)
        self.assertEqual(
            arch1, ArchitectureRegistry.get_by_pxealias("archibald")
        )

    def test_get_by_pxealias_returns_None_if_none_matching(self):
        arch1 = Architecture(
            name="arch1",
            description="arch1",
            pxealiases=["archibald", "reginald"],
        )
        arch2 = Architecture(name="arch2", description="arch2")
        ArchitectureRegistry.register_item("arch1", arch1)
        ArchitectureRegistry.register_item("arch2", arch2)
        self.assertIsNone(ArchitectureRegistry.get_by_pxealias("stinkywinky"))
