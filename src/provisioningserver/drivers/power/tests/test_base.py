# Copyright 2014-2021 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `provisioningserver.drivers.power`."""


import random
from unittest.mock import call, sentinel

from jsonschema import validate
from twisted.internet import reactor
from twisted.internet.defer import inlineCallbacks, succeed

from maastesting import get_testing_timeout
from maastesting.factory import factory
from maastesting.runtest import MAASTwistedRunTest
from maastesting.testcase import MAASTestCase
from provisioningserver.drivers import make_setting_field, power
from provisioningserver.drivers.power import (
    get_error_message,
    JSON_POWER_DRIVER_SCHEMA,
    PowerActionError,
    PowerAuthError,
    PowerConnError,
    PowerDriver,
    PowerDriverBase,
    PowerError,
    PowerFatalError,
    PowerSettingError,
    PowerToolError,
)
from provisioningserver.utils.twisted import asynchronous

TIMEOUT = get_testing_timeout()


class FakePowerDriverBase(PowerDriverBase):
    name = ""
    chassis = False
    can_probe = False
    can_set_boot_order = False
    description = ""
    settings = []
    ip_extractor = None
    queryable = True

    def __init__(self, name, description, settings, chassis=False):
        self.name = name
        self.description = description
        self.settings = settings
        self.chassis = chassis
        super().__init__()

    def on(self, system_id, context):
        raise NotImplementedError

    def off(self, system_id, context):
        raise NotImplementedError

    def cycle(self, system_id, context):
        raise NotImplementedError

    def query(self, system_id, context):
        raise NotImplementedError

    def reset(self, system_id, context):
        raise NotImplementedError

    def detect_missing_packages(self):
        return []


def make_power_driver_base(
    name=None, description=None, settings=None, chassis=False
):
    if name is None:
        name = factory.make_name("diskless")
    if description is None:
        description = factory.make_name("description")
    if settings is None:
        settings = []
    return FakePowerDriverBase(name, description, settings, chassis)


class TestFakePowerDriverBase(MAASTestCase):
    def test_attributes(self):
        fake_name = factory.make_name("name")
        fake_description = factory.make_name("description")
        fake_setting = factory.make_name("setting")
        fake_settings = [
            make_setting_field(fake_setting, fake_setting.title())
        ]
        fake_driver = FakePowerDriverBase(
            fake_name, fake_description, fake_settings
        )
        self.assertEqual(fake_driver.name, fake_name)
        self.assertEqual(fake_driver.description, fake_description)
        self.assertEqual(fake_driver.settings, fake_settings)

    def test_make_power_driver_base(self):
        fake_name = factory.make_name("name")
        fake_description = factory.make_name("description")
        fake_setting = factory.make_name("setting")
        fake_settings = [
            make_setting_field(fake_setting, fake_setting.title())
        ]
        fake_driver = make_power_driver_base(
            name=fake_name,
            description=fake_description,
            settings=fake_settings,
        )
        self.assertEqual(fake_driver.name, fake_name)
        self.assertEqual(fake_driver.description, fake_description)
        self.assertEqual(fake_driver.settings, fake_settings)

    def test_make_power_driver_base_makes_name_and_description(self):
        fake_driver = make_power_driver_base()
        self.assertNotEqual("", fake_driver.name)
        self.assertNotEqual("", fake_driver.description)

    def test_on_raises_not_implemented(self):
        fake_driver = make_power_driver_base()
        self.assertRaises(
            NotImplementedError,
            fake_driver.on,
            sentinel.system_id,
            sentinel.context,
        )

    def test_off_raises_not_implemented(self):
        fake_driver = make_power_driver_base()
        self.assertRaises(
            NotImplementedError,
            fake_driver.off,
            sentinel.system_id,
            sentinel.context,
        )

    def test_cycle_raises_not_implemented(self):
        fake_driver = make_power_driver_base()
        self.assertRaises(
            NotImplementedError,
            fake_driver.cycle,
            sentinel.system_id,
            sentinel.context,
        )

    def test_query_raises_not_implemented(self):
        fake_driver = make_power_driver_base()
        self.assertRaises(
            NotImplementedError,
            fake_driver.query,
            sentinel.system_id,
            sentinel.context,
        )

    def test_set_boot_order_raises_not_implemented(self):
        fake_driver = make_power_driver_base()
        self.assertRaises(
            NotImplementedError,
            fake_driver.set_boot_order,
            sentinel.system_id,
            sentinel.context,
            sentinel.order,
        )


class TestPowerDriverBase(MAASTestCase):
    def test_get_schema(self):
        fake_name = factory.make_name("name")
        fake_description = factory.make_name("description")
        fake_setting = factory.make_name("setting")
        fake_chassis = factory.pick_bool()
        fake_settings = [
            make_setting_field(fake_setting, fake_setting.title())
        ]
        fake_driver = make_power_driver_base(
            name=fake_name,
            description=fake_description,
            chassis=fake_chassis,
            settings=fake_settings,
        )
        self.assertEqual(
            {
                "driver_type": "power",
                "name": fake_name,
                "description": fake_description,
                "chassis": fake_chassis,
                "can_probe": False,
                "fields": fake_settings,
                "queryable": fake_driver.queryable,
                "missing_packages": fake_driver.detect_missing_packages(),
            },
            fake_driver.get_schema(),
        )

    def test_get_schema_returns_valid_schema(self):
        fake_driver = make_power_driver_base()
        # doesn't raise ValidationError
        validate(fake_driver.get_schema(), JSON_POWER_DRIVER_SCHEMA)


class TestGetErrorMessage(MAASTestCase):
    scenarios = [
        (
            "auth",
            dict(
                exception=PowerAuthError("auth"),
                message="Could not authenticate to node's BMC: auth",
            ),
        ),
        (
            "conn",
            dict(
                exception=PowerConnError("conn"),
                message="Could not contact node's BMC: conn",
            ),
        ),
        (
            "setting",
            dict(
                exception=PowerSettingError("setting"),
                message="Missing or invalid power setting: setting",
            ),
        ),
        (
            "tool",
            dict(
                exception=PowerToolError("tool"),
                message="Missing power tool: tool",
            ),
        ),
        (
            "action",
            dict(
                exception=PowerActionError("action"),
                message="Failed to complete power action: action",
            ),
        ),
        (
            "unknown",
            dict(
                exception=PowerError("unknown error"),
                message="Failed talking to node's BMC: unknown error",
            ),
        ),
    ]

    def test_return_msg(self):
        self.assertEqual(self.message, get_error_message(self.exception))


class FakePowerDriver(PowerDriver):
    name = ""
    chassis = False
    can_probe = False
    can_set_boot_order = False
    description = ""
    settings = []
    ip_extractor = None
    queryable = True

    def __init__(
        self, name, description, settings, wait_time=None, clock=reactor
    ):
        self.name = name
        self.description = description
        self.settings = settings
        if wait_time is not None:
            self.wait_time = wait_time
        super().__init__(clock)

    def detect_missing_packages(self):
        return []

    def power_on(self, system_id, context):
        raise NotImplementedError

    def power_off(self, system_id, context):
        raise NotImplementedError

    def power_query(self, system_id, context):
        raise NotImplementedError

    def power_reset(self, system_id, context):
        raise NotImplementedError


def make_power_driver(
    name=None, description=None, settings=None, wait_time=None, clock=reactor
):
    if name is None:
        name = factory.make_name("diskless")
    if description is None:
        description = factory.make_name("description")
    if settings is None:
        settings = []
    return FakePowerDriver(
        name, description, settings, wait_time=wait_time, clock=clock
    )


class AsyncFakePowerDriver(FakePowerDriver):
    def __init__(
        self,
        name,
        description,
        settings,
        wait_time=None,
        clock=reactor,
        query_result=None,
    ):
        super().__init__(
            name, description, settings, wait_time=None, clock=reactor
        )
        self.power_query_result = query_result
        self.power_on_called = 0
        self.power_off_called = 0
        self.power_reset_called = 0

    @asynchronous
    def power_on(self, system_id, context):
        self.power_on_called += 1
        return succeed(None)

    @asynchronous
    def power_off(self, system_id, context):
        self.power_off_called += 1
        return succeed(None)

    @asynchronous
    def power_query(self, system_id, context):
        return succeed(self.power_query_result)

    @asynchronous
    def power_reset(self, system_id, context):
        self.power_reset_called += 1
        return succeed(None)


def make_async_power_driver(
    name=None,
    description=None,
    settings=None,
    wait_time=None,
    clock=reactor,
    query_result=None,
):
    if name is None:
        name = factory.make_name("diskless")
    if description is None:
        description = factory.make_name("description")
    if settings is None:
        settings = []
    return AsyncFakePowerDriver(
        name,
        description,
        settings,
        wait_time=wait_time,
        clock=clock,
        query_result=query_result,
    )


class TestPowerDriverPowerAction(MAASTestCase):
    run_tests_with = MAASTwistedRunTest.make_factory(timeout=TIMEOUT)

    scenarios = [
        ("on", dict(action="on", action_func="power_on", bad_state="off")),
        ("off", dict(action="off", action_func="power_off", bad_state="on")),
    ]

    def make_error_message(self):
        error = factory.make_name("msg")
        self.patch(power, "get_error_message").return_value = error
        return error

    @inlineCallbacks
    def test_success(self):
        system_id = factory.make_name("system_id")
        context = {"context": factory.make_name("context")}
        driver = make_power_driver(wait_time=[0])
        self.patch(driver, self.action_func)
        self.patch(driver, "power_query").return_value = self.action
        method = getattr(driver, self.action)
        result = yield method(system_id, context)
        self.assertIsNone(result)

    @inlineCallbacks
    def test_success_async(self):
        system_id = factory.make_name("system_id")
        context = {"context": factory.make_name("context")}
        mock_deferToThread = self.patch(power, "deferToThread")
        driver = make_async_power_driver(
            wait_time=[0], query_result=self.action
        )
        method = getattr(driver, self.action)
        result = yield method(system_id, context)
        self.assertIsNone(result)
        call_count = getattr(driver, "%s_called" % self.action_func)
        self.assertEqual(1, call_count)
        mock_deferToThread.assert_not_called()

    @inlineCallbacks
    def test_handles_fatal_error_on_first_call(self):
        system_id = factory.make_name("system_id")
        context = {"context": factory.make_name("context")}
        driver = make_power_driver(wait_time=[0, 0])
        mock_on = self.patch(driver, self.action_func)
        mock_on.side_effect = [PowerFatalError(), None]
        mock_query = self.patch(driver, "power_query")
        mock_query.return_value = self.action
        method = getattr(driver, self.action)
        with self.assertRaisesRegex(PowerFatalError, "^$"):
            yield method(system_id, context)
        mock_query.assert_not_called()

    @inlineCallbacks
    def test_handles_non_fatal_error_on_first_call(self):
        system_id = factory.make_name("system_id")
        context = {"context": factory.make_name("context")}
        driver = make_power_driver(wait_time=[0, 0])
        mock_on = self.patch(driver, self.action_func)
        mock_on.side_effect = [PowerError(), None]
        mock_query = self.patch(driver, "power_query")
        mock_query.return_value = self.action
        method = getattr(driver, self.action)
        result = yield method(system_id, context)
        mock_query.assert_called_once_with(system_id, context)
        self.assertIsNone(result)

    @inlineCallbacks
    def test_handles_non_fatal_error_and_holds_error(self):
        system_id = factory.make_name("system_id")
        context = {"context": factory.make_name("context")}
        driver = make_power_driver(wait_time=[0])
        error_msg = factory.make_name("error")
        self.patch(driver, self.action_func)
        mock_query = self.patch(driver, "power_query")
        mock_query.side_effect = PowerError(error_msg)
        method = getattr(driver, self.action)
        with self.assertRaisesRegex(PowerError, f"^{error_msg}$"):
            yield method(system_id, context)
        mock_query.assert_called_once_with(system_id, context)

    @inlineCallbacks
    def test_handles_non_fatal_error(self):
        system_id = factory.make_name("system_id")
        context = {"context": factory.make_name("context")}
        driver = make_power_driver(wait_time=[0])
        mock_on = self.patch(driver, self.action_func)
        mock_on.side_effect = PowerError("foo")
        method = getattr(driver, self.action)
        with self.assertRaisesRegex(PowerError, "foo"):
            yield method(system_id, context)

    @inlineCallbacks
    def test_handles_fails_to_complete_power_action_in_time(self):
        system_id = factory.make_name("system_id")
        context = {"context": factory.make_name("context")}
        driver = make_power_driver(wait_time=[0])
        self.patch(driver, self.action_func)
        mock_query = self.patch(driver, "power_query")
        mock_query.return_value = self.bad_state
        method = getattr(driver, self.action)
        with self.assertRaisesRegex(
            PowerError,
            f"Failed to power {system_id}. BMC never transitioned from {self.bad_state} to {self.action}",
        ):
            yield method(system_id, context)

    @inlineCallbacks
    def test_doesnt_power_query_if_unqueryable(self):
        system_id = factory.make_name("system_id")
        context = {"context": factory.make_name("context")}
        driver = make_power_driver(wait_time=[0])
        driver.queryable = False
        self.patch(driver, self.action_func)
        mock_query = self.patch(driver, "power_query")
        method = getattr(driver, self.action)
        yield method(system_id, context)
        mock_query.assert_not_called()


class TestPowerDriverCycle(MAASTestCase):
    run_tests_with = MAASTwistedRunTest.make_factory(timeout=TIMEOUT)

    @inlineCallbacks
    def test_cycles_power_when_node_is_powered_on(self):
        system_id = factory.make_name("system_id")
        context = {"context": factory.make_name("context")}
        driver = make_power_driver()
        mock_perform_power = self.patch(driver, "perform_power")
        self.patch(driver, "power_query").return_value = "on"
        yield driver.cycle(system_id, context)
        mock_perform_power.assert_has_calls(
            [
                call(driver.power_off, "off", system_id, context),
                call(driver.power_on, "on", system_id, context),
            ]
        )

    @inlineCallbacks
    def test_cycles_power_when_node_is_powered_off(self):
        system_id = factory.make_name("system_id")
        context = {"context": factory.make_name("context")}
        driver = make_power_driver()
        mock_perform_power = self.patch(driver, "perform_power")
        self.patch(driver, "power_query").return_value = "off"
        yield driver.cycle(system_id, context)
        mock_perform_power.assert_called_once_with(
            driver.power_on, "on", system_id, context
        )


class TestPowerDriverQuery(MAASTestCase):
    run_tests_with = MAASTwistedRunTest.make_factory(timeout=TIMEOUT)

    def setUp(self):
        super().setUp()
        self.patch(power, "pause")

    @inlineCallbacks
    def test_returns_state(self):
        system_id = factory.make_name("system_id")
        context = {"context": factory.make_name("context")}
        driver = make_power_driver()
        state = factory.make_name("state")
        self.patch(driver, "power_query").return_value = state
        output = yield driver.query(system_id, context)
        self.assertEqual(state, output)

    @inlineCallbacks
    def test_retries_on_failure_then_returns_state(self):
        driver = make_power_driver()
        self.patch(driver, "power_query").side_effect = [
            PowerError("one"),
            PowerError("two"),
            sentinel.state,
        ]
        output = yield driver.query(sentinel.system_id, sentinel.context)
        self.assertEqual(sentinel.state, output)

    @inlineCallbacks
    def test_raises_last_exception_after_all_retries_fail(self):
        wait_time = [random.randrange(1, 10) for _ in range(3)]
        driver = make_power_driver(wait_time=wait_time)
        exception_types = list(
            factory.make_exception_type((PowerError,)) for _ in wait_time
        )
        self.patch(driver, "power_query").side_effect = exception_types
        with self.assertRaisesRegex(exception_types[-1], "^$"):
            yield driver.query(sentinel.system_id, sentinel.context)

    @inlineCallbacks
    def test_pauses_between_retries(self):
        wait_time = [random.randrange(1, 10) for _ in range(3)]
        driver = make_power_driver(wait_time=wait_time)
        self.patch(driver, "power_query").side_effect = PowerError
        with self.assertRaisesRegex(PowerError, "^$"):
            yield driver.query(sentinel.system_id, sentinel.context)
        power.pause.assert_has_calls(
            [call(wait, reactor) for wait in wait_time]
        )
