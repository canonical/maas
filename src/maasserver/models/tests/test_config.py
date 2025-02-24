# Copyright 2012-2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for the `Config` class and friends."""

from django.db import IntegrityError
from django.http import HttpRequest
from fixtures import TestWithFixtures

from maascommon.events import AUDIT
from maascommon.workflows.dhcp import (
    CONFIGURE_DHCP_WORKFLOW_NAME,
    ConfigureDHCPParam,
)
from maasserver.enum import ENDPOINT_CHOICES
from maasserver.models import Config, Event, signals
import maasserver.models.config
from maasserver.models.config import ensure_uuid_in_config
from maasserver.models.vlan import VLAN
from maasserver.secrets import SecretManager
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.utils.orm import post_commit_hooks
from maasservicelayer.models.configurations import ConfigFactory
from provisioningserver.utils.testing import MAASIDFixture


def _get_default_config():
    models = ConfigFactory.ALL_CONFIGS.values()
    return {config.name: config.default for config in models}


class TestConfigDefault(MAASServerTestCase, TestWithFixtures):
    def test_defaults(self):
        expected = _get_default_config()
        observed = {name: Config.objects.get_config(name) for name in expected}

        # Test isolation is not what it ought to be, so we have to exclude
        # rpc_shared_secret here for now. Attempts to improve isolation have
        # so far resulted in random unreproducible test failures. See the
        # merge proposal for lp:~allenap/maas/increased-test-isolation.
        self.assertIn("rpc_shared_secret", expected)
        del expected["rpc_shared_secret"]
        self.assertIn("rpc_shared_secret", observed)
        del observed["rpc_shared_secret"]

        # completed_intro is set to True in all tests so that URL manipulation
        # in the middleware does not occur. We check that it is True and
        # remove it from the expected and observed.
        self.assertTrue(observed["completed_intro"])
        del expected["completed_intro"]
        del observed["completed_intro"]

        self.assertEqual(expected, observed)


class CallRecorder:
    """A utility class which tracks the calls to its 'call' method and
    stores the arguments given to 'call' in 'self.calls'.
    """

    def __init__(self):
        self.calls = []

    def __call__(self, *args, **kwargs):
        self.calls.append([args, kwargs])


class TestConfig(MAASServerTestCase):
    def test_config_name_uniqueness_enforced(self):
        name = factory.make_name("name")
        Config.objects.create(name=name, value=factory.make_name("value"))
        self.assertRaises(
            IntegrityError,
            Config.objects.create,
            name=name,
            value=factory.make_name("value"),
        )

    def test_manager_get_config_found(self):
        Config.objects.create(name="name", value="config")
        config = Config.objects.get_config("name")
        self.assertEqual("config", config)

    def test_manager_get_config_not_found(self):
        config = Config.objects.get_config("name", "default value")
        self.assertEqual("default value", config)

    def test_manager_get_config_not_found_none(self):
        config = Config.objects.get_config("name")
        self.assertIsNone(config)

    def test_manager_get_configs_returns_configs_dict(self):
        expected = _get_default_config()
        # Only get a subset of all the configs.
        expected_names = list(expected)[:5]
        # Set a config value to test that is over the default.
        other_value = factory.make_name("value")
        Config.objects.set_config(expected_names[0], other_value)
        observed = Config.objects.get_configs(expected_names)
        expected_dict = {expected_names[0]: other_value}
        expected_dict.update(
            {
                name: expected[name]
                for name in expected_names
                if name != expected_names[0]
            }
        )
        self.assertEqual(expected_dict, observed)

    def test_manager_set_config_creates_config(self):
        Config.objects.set_config("name", "config1")
        Config.objects.set_config("name", "config2")
        self.assertSequenceEqual(
            ["config2"],
            [config.value for config in Config.objects.filter(name="name")],
        )

    def test_manager_set_config_for_secret_creates_secret(self):
        Config.objects.set_config("rpc_shared_secret", "abcd")
        self.assertEqual(
            SecretManager().get_simple_secret("rpc-shared"), "abcd"
        )

    def test_manager_set_config_creates_audit_event(self):
        user = factory.make_User()
        request = HttpRequest()
        request.user = user
        endpoint = factory.pick_choice(ENDPOINT_CHOICES)
        Config.objects.set_config("name", "value", endpoint, request)
        event = Event.objects.get(type__level=AUDIT)
        self.assertIsNotNone(event)
        self.assertEqual(
            event.description,
            "Updated configuration setting 'name' to 'value'.",
        )

    def test_manager_config_changed_connect_connects(self):
        recorder = CallRecorder()
        name = factory.make_string()
        value = factory.make_string()
        Config.objects.config_changed_connect(name, recorder)
        Config.objects.set_config(name, value)
        config = Config.objects.get(name=name)

        self.assertEqual(1, len(recorder.calls))
        self.assertEqual((Config, config, True), recorder.calls[0][0])

    def test_manager_config_changed_connect_connects_multiple(self):
        recorder = CallRecorder()
        recorder2 = CallRecorder()
        name = factory.make_string()
        value = factory.make_string()
        Config.objects.config_changed_connect(name, recorder)
        Config.objects.config_changed_connect(name, recorder2)
        Config.objects.set_config(name, value)

        self.assertEqual(1, len(recorder.calls))
        self.assertEqual(1, len(recorder2.calls))

    def test_manager_config_changed_connect_connects_multiple_same(self):
        # If the same method is connected twice, it will only get called
        # once.
        recorder = CallRecorder()
        name = factory.make_string()
        value = factory.make_string()
        Config.objects.config_changed_connect(name, recorder)
        Config.objects.config_changed_connect(name, recorder)
        Config.objects.set_config(name, value)

        self.assertEqual(1, len(recorder.calls))

    def test_manager_config_changed_connect_connects_by_config_name(self):
        recorder = CallRecorder()
        name = factory.make_string()
        value = factory.make_string()
        Config.objects.config_changed_connect(name, recorder)
        another_name = factory.make_string()
        Config.objects.set_config(another_name, value)

        self.assertEqual(0, len(recorder.calls))

    def test_manager_config_changed_disconnect_disconnects(self):
        recorder = CallRecorder()
        name = factory.make_string()
        value = factory.make_string()
        Config.objects.config_changed_connect(name, recorder)
        Config.objects.config_changed_disconnect(name, recorder)
        Config.objects.set_config(name, value)

        self.assertEqual([], recorder.calls)


class TestSettingConfig(MAASServerTestCase):
    """Testing of the :class:`Config` model and setting each option."""

    scenarios = tuple(
        (name, {"name": name, "value": value})
        for name, value in _get_default_config().items()
    )

    def setUp(self):
        super().setUp()
        # Some of these setting we have to be careful about.
        if self.name in {"enable_http_proxy", "http_proxy"}:
            manager = signals.bootsources.signals
            self.addCleanup(manager.enable)
            manager.disable()

    def test_can_be_initialised_to_None_without_crashing(self):
        Config.objects.set_config(self.name, None)
        self.assertIsNone(Config.objects.get_config(self.name))

    def test_can_be_modified_from_None_without_crashing(self):
        Config.objects.set_config(self.name, None)
        Config.objects.set_config(self.name, self.value)
        self.assertEqual(self.value, Config.objects.get_config(self.name))

    def test_changing_ntp_servers_calls_configure_dhcp(self):
        mock_start_workflow = self.patch(
            maasserver.models.config, "start_workflow"
        )

        factory.make_VLAN(dhcp_on=True)

        with post_commit_hooks:
            Config.objects.set_config("ntp_servers", "127.0.0.1")

        mock_start_workflow.assert_called_once_with(
            workflow_name=CONFIGURE_DHCP_WORKFLOW_NAME,
            param=ConfigureDHCPParam(
                vlan_ids=[
                    vlan.id for vlan in VLAN.objects.filter(dhcp_on=True)
                ]
            ),
            task_queue="region",
        )

    def test_changing_ntp_external_only_calls_configure_dhcp(self):
        mock_start_workflow = self.patch(
            maasserver.models.config, "start_workflow"
        )

        factory.make_VLAN(dhcp_on=True)

        with post_commit_hooks:
            Config.objects.set_config("ntp_external_only", True)

        mock_start_workflow.assert_called_once_with(
            workflow_name=CONFIGURE_DHCP_WORKFLOW_NAME,
            param=ConfigureDHCPParam(
                vlan_ids=[
                    vlan.id for vlan in VLAN.objects.filter(dhcp_on=True)
                ]
            ),
            task_queue="region",
        )


class TestEnsureUUIDInConfig(MAASServerTestCase):
    def test_create_and_store_uuid(self):
        region = factory.make_RegionController()
        self.useFixture(MAASIDFixture(region.system_id))
        self.assertIsNone(Config.objects.get_config("uuid"))
        created_uuid = ensure_uuid_in_config()
        config_uuid = Config.objects.get_config("uuid")
        self.assertEqual(created_uuid, config_uuid)

    def test_return_stored_uuid(self):
        region = factory.make_RegionController()
        self.useFixture(MAASIDFixture(region.system_id))
        created_uuid = ensure_uuid_in_config()
        config_uuid = Config.objects.get_config("uuid")
        stored_uuid = ensure_uuid_in_config()
        self.assertEqual(stored_uuid, config_uuid)
        self.assertEqual(created_uuid, stored_uuid)
