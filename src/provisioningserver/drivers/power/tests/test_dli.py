# Copyright 2015-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `provisioningserver.drivers.power.dli`."""

from random import choice
from unittest.mock import call, sentinel

from maastesting.factory import factory
from maastesting.testcase import MAASTestCase
from provisioningserver.drivers.power import dli as dli_module
from provisioningserver.drivers.power import PowerActionError, PowerError
from provisioningserver.utils.shell import (
    ExternalProcessError,
    get_env_with_locale,
    has_command_available,
)

DLI_QUERY_OUTPUT = b"""\
...
<!--
function reg() {
window.open('http://www.digital-loggers.com/register.html?SN=LPC751740');
}
//-->
</script>
</head>
<!-- state=%s lock=00 -->

<body alink="#0000FF" vlink="#0000FF">
<FONT FACE="Arial, Helvetica, Sans-Serif">
...
"""


class TestDLIPowerDriver(MAASTestCase):
    def test_missing_packages(self):
        mock = self.patch(has_command_available)
        mock.return_value = False
        driver = dli_module.DLIPowerDriver()
        missing = driver.detect_missing_packages()
        self.assertEqual(["wget"], missing)

    def test_no_missing_packages(self):
        mock = self.patch(has_command_available)
        mock.return_value = True
        driver = dli_module.DLIPowerDriver()
        missing = driver.detect_missing_packages()
        self.assertEqual([], missing)

    def test_set_outlet_state_calls_wget(self):
        driver = dli_module.DLIPowerDriver()
        env = get_env_with_locale()
        power_change = factory.make_name("power_change")
        outlet_id = choice(["1", "2", "3", "4", "5", "6", "7", "8"])
        power_user = factory.make_name("power_user")
        power_pass = factory.make_name("power_pass")
        power_address = factory.make_name("power_address")
        url = "http://{}:{}@{}/outlet?{}={}".format(
            power_user,
            power_pass,
            power_address,
            outlet_id,
            power_change,
        )
        call_and_check_mock = self.patch(dli_module, "call_and_check")

        driver._set_outlet_state(
            power_change, outlet_id, power_user, power_pass, power_address
        )

        call_and_check_mock.assert_called_once_with(
            ["wget", "--auth-no-challenge", "-O", "/dev/null", url],
            env=env,
        )

    def test_set_outlet_state_crashes_when_wget_exits_nonzero(self):
        driver = dli_module.DLIPowerDriver()
        call_and_check_mock = self.patch(dli_module, "call_and_check")
        call_and_check_mock.side_effect = ExternalProcessError(
            1, "dli something"
        )
        self.assertRaises(
            PowerActionError,
            driver._set_outlet_state,
            sentinel.power_change,
            sentinel.outlet_id,
            sentinel.power_use,
            sentinel.power_pass,
            sentinel.power_address,
        )

    def test_query_outlet_state_queries_on(self):
        driver = dli_module.DLIPowerDriver()
        env = get_env_with_locale()
        outlet_id = choice(["1", "2", "3", "4", "5", "6", "7", "8"])
        power_user = factory.make_name("power_user")
        power_pass = factory.make_name("power_pass")
        power_address = factory.make_name("power_address")
        url = "http://{}:{}@{}/index.htm".format(
            power_user,
            power_pass,
            power_address,
        )
        call_and_check_mock = self.patch(dli_module, "call_and_check")
        call_and_check_mock.return_value = DLI_QUERY_OUTPUT % b"ff"

        result = driver._query_outlet_state(
            outlet_id, power_user, power_pass, power_address
        )

        call_and_check_mock.assert_called_once_with(
            ["wget", "--auth-no-challenge", "-qO-", url], env=env
        )
        self.assertEqual(result, "on")

    def test_query_outlet_state_queries_off(self):
        driver = dli_module.DLIPowerDriver()
        env = get_env_with_locale()
        outlet_id = choice(["1", "2", "3", "4", "5", "6", "7", "8"])
        power_user = factory.make_name("power_user")
        power_pass = factory.make_name("power_pass")
        power_address = factory.make_name("power_address")
        url = "http://{}:{}@{}/index.htm".format(
            power_user,
            power_pass,
            power_address,
        )
        call_and_check_mock = self.patch(dli_module, "call_and_check")
        call_and_check_mock.return_value = DLI_QUERY_OUTPUT % b"00"

        result = driver._query_outlet_state(
            outlet_id, power_user, power_pass, power_address
        )

        call_and_check_mock.assert_called_once_with(
            ["wget", "--auth-no-challenge", "-qO-", url], env=env
        )
        self.assertEqual(result, "off")

    def test_query_outlet_state_crashes_when_state_not_found(self):
        driver = dli_module.DLIPowerDriver()
        call_and_check_mock = self.patch(dli_module, "call_and_check")
        call_and_check_mock.return_value = b"Rubbish"
        self.assertRaises(
            PowerError,
            driver._query_outlet_state,
            sentinel.outlet_id,
            sentinel.power_user,
            sentinel.power_pass,
            sentinel.power_address,
        )

    def test_query_outlet_state_crashes_when_wget_exits_nonzero(self):
        driver = dli_module.DLIPowerDriver()
        call_and_check_mock = self.patch(dli_module, "call_and_check")
        call_and_check_mock.side_effect = ExternalProcessError(
            1, "dli something"
        )
        self.assertRaises(
            PowerActionError,
            driver._query_outlet_state,
            sentinel.outlet_id,
            sentinel.power_user,
            sentinel.power_pass,
            sentinel.power_address,
        )

    def test_power_on(self):
        driver = dli_module.DLIPowerDriver()
        system_id = factory.make_name("system_id")
        context = {"context": factory.make_name("context")}
        _query_outlet_state_mock = self.patch(driver, "_query_outlet_state")
        _query_outlet_state_mock.side_effect = ("on", "off")
        _set_outlet_state_mock = self.patch(driver, "_set_outlet_state")
        self.patch(dli_module, "sleep")

        driver.power_on(system_id, context)

        _query_outlet_state_mock.assert_has_calls(
            [call(**context), call(**context)]
        )
        _set_outlet_state_mock.assert_has_calls(
            [call("OFF", **context), call("ON", **context)]
        )

    def test_power_on_raises_power_error(self):
        driver = dli_module.DLIPowerDriver()
        system_id = factory.make_name("system_id")
        context = {"outlet_id": factory.make_name("outlet_id")}
        _query_outlet_state_mock = self.patch(driver, "_query_outlet_state")
        _query_outlet_state_mock.side_effect = ("on", "not-off")
        _set_outlet_state_mock = self.patch(driver, "_set_outlet_state")
        self.patch(dli_module, "sleep")

        self.assertRaises(PowerError, driver.power_on, system_id, context)
        _query_outlet_state_mock.assert_has_calls(
            [call(**context), call(**context)]
        )
        _set_outlet_state_mock.assert_called_once_with("OFF", **context)

    def test_power_off(self):
        driver = dli_module.DLIPowerDriver()
        system_id = factory.make_name("system_id")
        context = {"context": factory.make_name("context")}
        _set_outlet_state_mock = self.patch(driver, "_set_outlet_state")
        driver.power_off(system_id, context)
        _set_outlet_state_mock.assert_called_once_with("OFF", **context)

    def test_power_query(self):
        driver = dli_module.DLIPowerDriver()
        system_id = factory.make_name("system_id")
        context = {"context": factory.make_name("context")}
        _query_outlet_state_mock = self.patch(driver, "_query_outlet_state")
        driver.power_query(system_id, context)
        _query_outlet_state_mock.assert_called_once_with(**context)
