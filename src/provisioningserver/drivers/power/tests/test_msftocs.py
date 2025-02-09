# Copyright 2015-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `provisioningserver.drivers.power.msftocs`."""

from io import StringIO
from random import randint
from textwrap import dedent
from unittest.mock import call, Mock
import urllib.parse

from hypothesis import given, settings
from hypothesis.strategies import sampled_from
from twisted.internet.defer import inlineCallbacks
from twisted.internet.threads import deferToThread

from maastesting import get_testing_timeout
from maastesting.factory import factory
from maastesting.testcase import MAASTestCase, MAASTwistedRunTest
from provisioningserver.drivers.power import msftocs as msftocs_module
from provisioningserver.drivers.power import (
    PowerActionError,
    PowerConnError,
    PowerFatalError,
)
from provisioningserver.drivers.power.msftocs import (
    MicrosoftOCSPowerDriver,
    MicrosoftOCSState,
    probe_and_enlist_msftocs,
)
from provisioningserver.utils.twisted import asynchronous

XMLNS = "http://schemas.datacontract.org/2004/07/Microsoft.GFS.WCS.Contracts"
XMLNS_I = "http://www.w3.org/2001/XMLSchema-instance"


def make_context():
    """Make and return a power parameters context."""
    return {
        "power_address": factory.make_ipv4_address(),
        "power_port": "%d" % randint(2000, 4000),
        "power_user": factory.make_name("power_user"),
        "power_pass": factory.make_name("power_pass"),
        "blade_id": "%d" % randint(1, 24),
    }


class TestMicrosoftOCSPowerDriver(MAASTestCase):
    def test_missing_packages(self):
        # there's nothing to check for, just confirm it returns []
        driver = MicrosoftOCSPowerDriver()
        missing = driver.detect_missing_packages()
        self.assertEqual([], missing)

    def test_extract_from_response_finds_element_content(self):
        driver = MicrosoftOCSPowerDriver()
        response = dedent(
            """
            <a xmlns='%s' xmlns:i='%s'>
                <b/>
                <c/>
                <d>Test</d>
            </a>
        """
            % (XMLNS, XMLNS_I)
        )
        element_tag = "d"
        expected = "Test"
        output = driver.extract_from_response(response, element_tag)
        self.assertEqual(expected, output)

    def test_get_gets_response(self):
        driver = MicrosoftOCSPowerDriver()
        context = make_context()
        command = factory.make_string()
        params = [factory.make_string() for _ in range(3)]
        expected = dedent(
            """
            <ChassisInfoResponse xmlns='%s' xmlns:i='%s'>
                <bladeCollections>
                    <BladeInfo>
                    </BladeInfo>
                </bladeCollections>
            </ChassisInfoResponse>
        """
            % (XMLNS, XMLNS_I)
        )
        response = StringIO(expected)
        self.patch(urllib.request, "urlopen", Mock(return_value=response))
        output = driver.get(command, context, params)
        self.assertEqual(output, expected)

    def test_get_crashes_on_http_error(self):
        driver = MicrosoftOCSPowerDriver()
        context = make_context()
        command = factory.make_string()
        mock_urlopen = self.patch(urllib.request, "urlopen")
        mock_urlopen.side_effect = urllib.error.HTTPError(
            None, None, None, None, None
        )
        self.assertRaises(PowerConnError, driver.get, command, context)

    def test_get_crashes_on_url_error(self):
        driver = MicrosoftOCSPowerDriver()
        context = make_context()
        command = factory.make_string()
        mock_urlopen = self.patch(urllib.request, "urlopen")
        mock_urlopen.side_effect = urllib.error.URLError("URL Error")
        self.assertRaises(PowerConnError, driver.get, command, context)

    def test_set_next_boot_device_sets_device(self):
        driver = MicrosoftOCSPowerDriver()
        context = make_context()
        bootType = "2"
        boot_uefi = "false"
        boot_persistent = "false"
        params = [
            "bladeid=%s" % context["blade_id"],
            "bootType=%s" % bootType,
            "uefi=%s" % boot_uefi,
            "persistent=%s" % boot_persistent,
        ]
        mock_get = self.patch(driver, "get")
        driver.set_next_boot_device(context, pxe=True)
        mock_get.assert_called_once_with("SetNextBoot", context, params)

    def test_get_blades_gets_blades(self):
        driver = MicrosoftOCSPowerDriver()
        context = make_context()
        response = dedent(
            """
            <ChassisInfoResponse xmlns='%s' xmlns:i='%s'>
                <bladeCollections>
                    <BladeInfo>
                        <completionCode>Success</completionCode>
                        <apiVersion>1</apiVersion>
                        <statusDescription/>
                        <bladeNumber>11</bladeNumber>
                        <bladeGuid></bladeGuid>
                        <bladeName>BLADE11</bladeName>
                        <powerState>ON</powerState>
                        <bladeMacAddress>
                            <NicInfo>
                                <completionCode>Success</completionCode>
                                <apiVersion>1</apiVersion>
                                <statusDescription/>
                                <deviceId>1</deviceId>
                                <macAddress>F4:52:14:D6:70:98</macAddress>
                            </NicInfo>
                            <NicInfo>
                                <completionCode>Success</completionCode>
                                <apiVersion>1</apiVersion>
                                <statusDescription></statusDescription>
                                <deviceId>2</deviceId>
                                <macAddress/>
                            </NicInfo>
                        </bladeMacAddress>
                    </BladeInfo>
                </bladeCollections>
            </ChassisInfoResponse>
        """
            % (XMLNS, XMLNS_I)
        )
        mock_get = self.patch(driver, "get", Mock(return_value=response))
        expected = {"11": ["F4:52:14:D6:70:98"]}
        output = driver.get_blades(context)

        self.assertEqual(output, expected)
        mock_get.assert_called_once_with("GetChassisInfo", context)

    def test_power_on_powers_on_blade(self):
        driver = MicrosoftOCSPowerDriver()
        context = make_context()
        system_id = factory.make_name("system_id")
        mock_power_query = self.patch(driver, "power_query")
        mock_power_query.return_value = "on"
        mock_power_off = self.patch(driver, "power_off")
        mock_set_next_boot_device = self.patch(driver, "set_next_boot_device")
        mock_get = self.patch(driver, "get")
        driver.power_on(system_id, context)

        mock_power_query.assert_called_once_with(system_id, context)
        mock_power_off.assert_called_once_with(system_id, context)
        mock_set_next_boot_device.assert_has_calls(
            [call(context, persistent=True), call(context, pxe=True)]
        )
        mock_get.assert_called_once_with(
            "SetBladeOn", context, ["bladeid=%s" % context["blade_id"]]
        )

    def test_power_on_crashes_for_connection_error(self):
        driver = MicrosoftOCSPowerDriver()
        context = make_context()
        system_id = factory.make_name("system_id")
        self.patch(driver, "power_query", Mock(return_value="off"))
        self.patch(driver, "set_next_boot_device")
        mock_get = self.patch(driver, "get")
        mock_get.side_effect = PowerConnError("Connection Error")
        self.assertRaises(
            PowerActionError, driver.power_on, system_id, context
        )

    def test_power_off_powers_off_blade(self):
        driver = MicrosoftOCSPowerDriver()
        context = make_context()
        system_id = factory.make_name("system_id")
        mock_get = self.patch(driver, "get")
        driver.power_off(system_id, context)
        mock_get.assert_called_once_with(
            "SetBladeOff", context, ["bladeid=%s" % context["blade_id"]]
        )

    def test_power_off_crashes_for_connection_error(self):
        driver = MicrosoftOCSPowerDriver()
        context = make_context()
        system_id = factory.make_name("system_id")
        mock_get = self.patch(driver, "get")
        mock_get.side_effect = PowerConnError("Connection Error")
        self.assertRaises(
            PowerActionError, driver.power_off, system_id, context
        )

    @given(sampled_from([MicrosoftOCSState.ON, MicrosoftOCSState.OFF]))
    @settings(deadline=None)
    def test_power_query_returns_power_state(self, power_state):
        def get_msftocs_state(power_state):
            if power_state == MicrosoftOCSState.OFF:
                return "off"
            elif power_state == MicrosoftOCSState.ON:
                return "on"

        driver = MicrosoftOCSPowerDriver()
        context = make_context()
        system_id = factory.make_name("system_id")
        mock_extract_from_response = self.patch(
            driver, "extract_from_response"
        )
        mock_extract_from_response.return_value = power_state
        self.patch(driver, "get")
        output = driver.power_query(system_id, context)
        self.assertEqual(get_msftocs_state(power_state), output)

    def test_power_query_crashes_for_connection_error(self):
        driver = MicrosoftOCSPowerDriver()
        context = make_context()
        system_id = factory.make_name("system_id")
        mock_extract_from_response = self.patch(
            driver, "extract_from_response"
        )
        mock_extract_from_response.side_effect = PowerConnError(
            "Connection Error"
        )
        self.patch(driver, "get")
        self.assertRaises(
            PowerActionError, driver.power_query, system_id, context
        )

    def test_power_query_crashes_when_unable_to_find_match(self):
        driver = MicrosoftOCSPowerDriver()
        context = make_context()
        system_id = factory.make_name("system_id")
        mock_extract_from_response = self.patch(
            driver, "extract_from_response"
        )
        mock_extract_from_response.return_value = "Rubbish"
        self.patch(driver, "get")
        self.assertRaises(
            PowerFatalError, driver.power_query, system_id, context
        )


class TestMicrosoftOCSProbeAndEnlist(MAASTestCase):
    """Tests for `probe_and_enlist_msftocs`."""

    run_tests_with = MAASTwistedRunTest.make_factory(
        timeout=get_testing_timeout()
    )

    @inlineCallbacks
    def test_probe_and_enlist_msftocs_probes_and_enlists(self):
        context = make_context()
        user = factory.make_name("user")
        system_id = factory.make_name("system_id")
        domain = factory.make_name("domain")
        macs = [factory.make_mac_address() for _ in range(3)]
        mock_get_blades = self.patch(MicrosoftOCSPowerDriver, "get_blades")
        mock_get_blades.return_value = {"%s" % context["blade_id"]: macs}
        self.patch(MicrosoftOCSPowerDriver, "set_next_boot_device")
        mock_create_node = self.patch(msftocs_module, "create_node")
        mock_create_node.side_effect = asynchronous(lambda *args: system_id)
        mock_commission_node = self.patch(msftocs_module, "commission_node")

        yield deferToThread(
            probe_and_enlist_msftocs,
            user,
            context["power_address"],
            int(context["power_port"]),
            context["power_user"],
            context["power_pass"],
            True,
            domain,
        )

        (
            mock_create_node.assert_called_once_with(
                macs, "amd64", "msftocs", context, domain
            ),
        )
        mock_commission_node.assert_called_once_with(system_id, user)

    @inlineCallbacks
    def test_probe_and_enlist_msftocs_get_blades_failure_server_error(self):
        user = factory.make_name("user")
        context = make_context()
        mock_get_blades = self.patch(MicrosoftOCSPowerDriver, "get_blades")
        mock_get_blades.side_effect = urllib.error.URLError("URL Error")

        with self.assertRaisesRegex(
            PowerFatalError,
            r"^Failed to probe nodes for Microsoft OCS with .* Server could not be reached: URL Error$",
        ):
            yield deferToThread(
                probe_and_enlist_msftocs,
                user,
                context["power_address"],
                int(context["power_port"]),
                context["power_user"],
                context["power_pass"],
            )

    @inlineCallbacks
    def test_probe_and_enlist_msftocs_get_blades_failure_http_error(self):
        user = factory.make_name("user")
        context = make_context()
        mock_get_blades = self.patch(MicrosoftOCSPowerDriver, "get_blades")
        mock_get_blades.side_effect = urllib.error.HTTPError(
            None, None, None, None, None
        )

        with self.assertRaisesRegex(
            PowerFatalError,
            r"^Failed to probe nodes for Microsoft OCS with .* HTTP error code: None$",
        ):
            yield deferToThread(
                probe_and_enlist_msftocs,
                user,
                context["power_address"],
                int(context["power_port"]),
                context["power_user"],
                context["power_pass"],
            )
