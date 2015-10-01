# Copyright 2014-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `provisioningserver.drivers.power`."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

import random

from maastesting.factory import factory
from maastesting.matchers import (
    MockCalledOnceWith,
    MockCallsMatch,
    MockNotCalled,
)
from maastesting.testcase import MAASTestCase
from mock import (
    call,
    sentinel,
)
from provisioningserver.drivers import (
    make_setting_field,
    power,
    validate_settings,
)
from provisioningserver.drivers.power import (
    get_error_message,
    PowerActionError,
    PowerAuthError,
    PowerConnError,
    PowerDriver,
    PowerDriverBase,
    PowerDriverRegistry,
    PowerError,
    PowerFatalError,
    PowerSettingError,
    PowerToolError,
)
from provisioningserver.utils.testing import RegistryFixture
from testtools.deferredruntest import AsynchronousDeferredRunTest
from testtools.matchers import Equals
from testtools.testcase import ExpectedException
from twisted.internet import reactor
from twisted.internet.defer import inlineCallbacks


class FakePowerDriverBase(PowerDriverBase):

    name = ""
    description = ""
    settings = []

    def __init__(self, name, description, settings):
        self.name = name
        self.description = description
        self.settings = settings
        super(FakePowerDriverBase, self).__init__()

    def on(self, system_id, **kwargs):
        raise NotImplementedError

    def off(self, system_id, **kwargs):
        raise NotImplementedError

    def query(self, system_id, **kwargs):
        raise NotImplementedError


def make_power_driver_base(name=None, description=None, settings=None):
    if name is None:
        name = factory.make_name('diskless')
    if description is None:
        description = factory.make_name('description')
    if settings is None:
        settings = []
    return FakePowerDriverBase(name, description, settings)


class TestFakePowerDriverBase(MAASTestCase):

    def test_attributes(self):
        fake_name = factory.make_name('name')
        fake_description = factory.make_name('description')
        fake_setting = factory.make_name('setting')
        fake_settings = [
            make_setting_field(
                fake_setting, fake_setting.title()),
            ]
        attributes = {
            'name': fake_name,
            'description': fake_description,
            'settings': fake_settings,
            }
        fake_driver = FakePowerDriverBase(
            fake_name, fake_description, fake_settings)
        self.assertAttributes(fake_driver, attributes)

    def test_make_power_driver_base(self):
        fake_name = factory.make_name('name')
        fake_description = factory.make_name('description')
        fake_setting = factory.make_name('setting')
        fake_settings = [
            make_setting_field(
                fake_setting, fake_setting.title()),
            ]
        attributes = {
            'name': fake_name,
            'description': fake_description,
            'settings': fake_settings,
            }
        fake_driver = make_power_driver_base(
            name=fake_name, description=fake_description,
            settings=fake_settings)
        self.assertAttributes(fake_driver, attributes)

    def test_make_power_driver_base_makes_name_and_description(self):
        fake_driver = make_power_driver_base()
        self.assertNotEqual("", fake_driver.name)
        self.assertNotEqual("", fake_driver.description)

    def test_on_raises_not_implemented(self):
        fake_driver = make_power_driver_base()
        self.assertRaises(
            NotImplementedError,
            fake_driver.on, sentinel.system_id)

    def test_off_raises_not_implemented(self):
        fake_driver = make_power_driver_base()
        self.assertRaises(
            NotImplementedError,
            fake_driver.off, sentinel.system_id)

    def test_query_raises_not_implemented(self):
        fake_driver = make_power_driver_base()
        self.assertRaises(
            NotImplementedError,
            fake_driver.query, sentinel.system_id)


class TestPowerDriverBase(MAASTestCase):

    def test_get_schema(self):
        fake_name = factory.make_name('name')
        fake_description = factory.make_name('description')
        fake_setting = factory.make_name('setting')
        fake_settings = [
            make_setting_field(
                fake_setting, fake_setting.title()),
            ]
        fake_driver = make_power_driver_base()
        self.assertItemsEqual({
            'name': fake_name,
            'description': fake_description,
            'fields': fake_settings,
            },
            fake_driver.get_schema())

    def test_get_schema_returns_valid_schema(self):
        fake_driver = make_power_driver_base()
        #: doesn't raise ValidationError
        validate_settings(fake_driver.get_schema())


class TestPowerDriverRegistry(MAASTestCase):

    def setUp(self):
        super(TestPowerDriverRegistry, self).setUp()
        # Ensure the global registry is empty for each test run.
        self.useFixture(RegistryFixture())

    def test_registry(self):
        self.assertItemsEqual([], PowerDriverRegistry)
        PowerDriverRegistry.register_item("driver", sentinel.driver)
        self.assertIn(
            sentinel.driver,
            (item for name, item in PowerDriverRegistry))

    def test_get_schema(self):
        fake_driver_one = make_power_driver_base()
        fake_driver_two = make_power_driver_base()
        PowerDriverRegistry.register_item(
            fake_driver_one.name, fake_driver_one)
        PowerDriverRegistry.register_item(
            fake_driver_two.name, fake_driver_two)
        self.assertItemsEqual([
            {
                'name': fake_driver_one.name,
                'description': fake_driver_one.description,
                'fields': [],
            },
            {
                'name': fake_driver_two.name,
                'description': fake_driver_two.description,
                'fields': [],
            }],
            PowerDriverRegistry.get_schema())


class TestGetErrorMessage(MAASTestCase):

    scenarios = [
        ('auth', dict(
            exception=PowerAuthError('auth'),
            message="Could not authenticate to node's BMC: auth",
            )),
        ('conn', dict(
            exception=PowerConnError('conn'),
            message="Could not contact node's BMC: conn",
            )),
        ('setting', dict(
            exception=PowerSettingError('setting'),
            message="Missing or invalid power setting: setting",
            )),
        ('tool', dict(
            exception=PowerToolError('tool'),
            message="Missing power tool: tool",
            )),
        ('action', dict(
            exception=PowerActionError('action'),
            message="Failed to complete power action: action",
            )),
        ('unknown', dict(
            exception=PowerError(),
            message="Failed talking to node's BMC for an unknown reason.",
            )),
    ]

    def test_return_msg(self):
        self.assertEqual(self.message, get_error_message(self.exception))


class FakePowerDriver(PowerDriver):

    name = ""
    description = ""
    settings = []

    def __init__(self, name, description, settings, wait_time=None,
                 clock=reactor):
        self.name = name
        self.description = description
        self.settings = settings
        if wait_time is not None:
            self.wait_time = wait_time
        super(FakePowerDriver, self).__init__(clock)

    def detect_missing_packages(self):
        raise NotImplementedError

    def power_on(self, system_id, **kwargs):
        raise NotImplementedError

    def power_off(self, system_id, **kwargs):
        raise NotImplementedError

    def power_query(self, system_id, **kwargs):
        raise NotImplementedError


def make_power_driver(name=None, description=None, settings=None,
                      wait_time=None, clock=reactor):
    if name is None:
        name = factory.make_name('diskless')
    if description is None:
        description = factory.make_name('description')
    if settings is None:
        settings = []
    return FakePowerDriver(
        name, description, settings, wait_time=wait_time, clock=clock)


class TestPowerDriverPowerAction(MAASTestCase):

    run_tests_with = AsynchronousDeferredRunTest.make_factory(timeout=5)

    scenarios = [
        ('on', dict(
            action='on', action_func='power_on', bad_state='off')),
        ('off', dict(
            action='off', action_func='power_off', bad_state='on')),
        ]

    def make_error_message(self):
        error = factory.make_name('msg')
        self.patch(power, 'get_error_message').return_value = error
        return error

    @inlineCallbacks
    def test_success(self):
        system_id = factory.make_name('system_id')
        driver = make_power_driver(wait_time=[0])
        self.patch(driver, self.action_func)
        self.patch(driver, 'power_query').return_value = self.action
        method = getattr(driver, self.action)
        result = yield method(system_id)
        self.assertEqual(result, None)

    @inlineCallbacks
    def test_handles_fatal_error_on_first_call(self):
        system_id = factory.make_name('system_id')
        driver = make_power_driver(wait_time=[0, 0])
        mock_on = self.patch(driver, self.action_func)
        mock_on.side_effect = [PowerFatalError(), None]
        mock_query = self.patch(driver, 'power_query')
        mock_query.return_value = self.action
        method = getattr(driver, self.action)
        with ExpectedException(PowerFatalError):
            yield method(system_id)
        self.expectThat(
            mock_query,
            Equals(MockNotCalled()))

    @inlineCallbacks
    def test_handles_non_fatal_error_on_first_call(self):
        system_id = factory.make_name('system_id')
        driver = make_power_driver(wait_time=[0, 0])
        mock_on = self.patch(driver, self.action_func)
        mock_on.side_effect = [PowerError(), None]
        mock_query = self.patch(driver, 'power_query')
        mock_query.return_value = self.action
        method = getattr(driver, self.action)
        result = yield method(system_id)
        self.expectThat(
            mock_query,
            Equals(MockCalledOnceWith(system_id)))
        self.expectThat(result, Equals(None))

    @inlineCallbacks
    def test_handles_non_fatal_error_and_holds_error(self):
        system_id = factory.make_name('system_id')
        driver = make_power_driver(wait_time=[0])
        error_msg = factory.make_name('error')
        self.patch(driver, self.action_func)
        mock_query = self.patch(driver, 'power_query')
        mock_query.side_effect = PowerError(error_msg)
        method = getattr(driver, self.action)
        with ExpectedException(PowerError):
            yield method(system_id)
        self.expectThat(
            mock_query,
            Equals(MockCalledOnceWith(system_id)))

    @inlineCallbacks
    def test_handles_non_fatal_error(self):
        system_id = factory.make_name('system_id')
        driver = make_power_driver(wait_time=[0])
        mock_on = self.patch(driver, self.action_func)
        mock_on.side_effect = PowerError()
        method = getattr(driver, self.action)
        with ExpectedException(PowerError):
            yield method(system_id)

    @inlineCallbacks
    def test_handles_fails_to_complete_power_action_in_time(self):
        system_id = factory.make_name('system_id')
        driver = make_power_driver(wait_time=[0])
        self.patch(driver, self.action_func)
        mock_query = self.patch(driver, 'power_query')
        mock_query.return_value = self.bad_state
        method = getattr(driver, self.action)
        with ExpectedException(PowerError):
            yield method(system_id)


class TestPowerDriverQuery(MAASTestCase):

    run_tests_with = AsynchronousDeferredRunTest.make_factory(timeout=5)

    def setUp(self):
        super(TestPowerDriverQuery, self).setUp()
        self.patch(power, "pause")

    @inlineCallbacks
    def test_returns_state(self):
        system_id = factory.make_name('system_id')
        driver = make_power_driver()
        state = factory.make_name('state')
        self.patch(driver, 'power_query').return_value = state
        output = yield driver.query(system_id)
        self.assertEqual(state, output)

    @inlineCallbacks
    def test_retries_on_failure_then_returns_state(self):
        driver = make_power_driver()
        self.patch(driver, 'power_query').side_effect = [
            PowerError("one"), PowerError("two"), sentinel.state]
        output = yield driver.query(sentinel.system_id)
        self.assertEqual(sentinel.state, output)

    @inlineCallbacks
    def test_raises_last_exception_after_all_retries_fail(self):
        wait_time = [random.randrange(1, 10) for _ in xrange(3)]
        driver = make_power_driver(wait_time=wait_time)
        exception_types = list(
            factory.make_exception_type((PowerError,))
            for _ in wait_time)
        self.patch(driver, 'power_query').side_effect = exception_types
        with ExpectedException(exception_types[-1]):
            yield driver.query(sentinel.system_id)

    @inlineCallbacks
    def test_pauses_between_retries(self):
        wait_time = [random.randrange(1, 10) for _ in xrange(3)]
        driver = make_power_driver(wait_time=wait_time)
        self.patch(driver, 'power_query').side_effect = PowerError
        with ExpectedException(PowerError):
            yield driver.query(sentinel.system_id)
        self.assertThat(power.pause, MockCallsMatch(
            *(call(wait, reactor) for wait in wait_time)))
