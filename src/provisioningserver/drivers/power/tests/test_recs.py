# Copyright 2017 christmann informationstechnik + medien GmbH & Co. KG. This
# software is licensed under the GNU Affero General Public License version 3
# (see the file LICENSE).

"""Tests for `provisioningserver.drivers.power.recs`."""


from io import StringIO
from textwrap import dedent
from unittest.mock import call, Mock
import urllib.parse

from twisted.internet.defer import inlineCallbacks
from twisted.internet.threads import deferToThread

from maastesting import get_testing_timeout
from maastesting.factory import factory
from maastesting.testcase import MAASTestCase, MAASTwistedRunTest
from provisioningserver.drivers.power import PowerConnError
from provisioningserver.drivers.power import recs as recs_module
from provisioningserver.drivers.power.recs import (
    extract_recs_parameters,
    probe_and_enlist_recs,
    RECSAPI,
    RECSError,
    RECSPowerDriver,
)
from provisioningserver.utils.shell import has_command_available
from provisioningserver.utils.twisted import asynchronous


class TestRECSPowerDriver(MAASTestCase):
    """Tests for RECS|Box custom hardware."""

    run_tests_with = MAASTwistedRunTest.make_factory(
        timeout=get_testing_timeout()
    )

    def test_no_missing_packages(self):
        mock = self.patch(has_command_available)
        mock.return_value = True
        driver = RECSPowerDriver()
        missing = driver.detect_missing_packages()
        self.assertEqual([], missing)

    def make_context(self):
        ip = factory.make_name("power_address")
        port = factory.pick_port()
        username = factory.make_name("power_user")
        password = factory.make_name("power_pass")
        node_id = factory.make_name("node_id")
        context = {
            "power_address": ip,
            "power_port": port,
            "power_user": username,
            "power_pass": password,
            "node_id": node_id,
        }
        return ip, port, username, password, node_id, context

    def test_extract_recs_parameters_extracts_parameters(self):
        ip, port, username, password, node_id, context = self.make_context()

        self.assertEqual(
            (ip, port, username, password, node_id),
            extract_recs_parameters(context),
        )

    def test_power_off_calls_power_control_recs(self):
        ip, port, username, password, node_id, context = self.make_context()
        recs_power_driver = RECSPowerDriver()
        power_control_recs_mock = self.patch(
            recs_power_driver, "power_control_recs"
        )
        recs_power_driver.power_off(context["node_id"], context)

        power_control_recs_mock.assert_called_once_with(
            ip, port, username, password, node_id, "off"
        )

    def test_power_on_calls_power_control_recs(self):
        ip, port, username, password, node_id, context = self.make_context()
        recs_power_driver = RECSPowerDriver()
        power_control_recs_mock = self.patch(
            recs_power_driver, "power_control_recs"
        )
        set_boot_source_recs_mock = self.patch(
            recs_power_driver, "set_boot_source_recs"
        )
        recs_power_driver.power_on(context["node_id"], context)

        power_control_recs_mock.assert_called_once_with(
            ip, port, username, password, node_id, "on"
        )
        set_boot_source_recs_mock.assert_has_calls(
            [
                call(ip, port, username, password, node_id, "HDD", True),
                call(ip, port, username, password, node_id, "PXE", False),
            ]
        )

    def test_power_query_calls_power_state_recs(self):
        ip, port, username, password, node_id, context = self.make_context()
        recs_power_driver = RECSPowerDriver()
        power_state_recs_mock = self.patch(
            recs_power_driver, "power_state_recs"
        )
        recs_power_driver.power_query(context["node_id"], context)

        power_state_recs_mock.assert_called_once_with(
            ip, port, username, password, node_id
        )

    def test_extract_from_response_finds_element_content(self):
        ip, port, username, password, node_id, context = self.make_context()
        api = RECSAPI(ip, port, username, password)
        response = dedent(
            """
            <node health="OK" id="RCU_84055620466592_BB_1_0" state="0" />
        """
        )
        attribute = "id"
        expected = "RCU_84055620466592_BB_1_0"
        output = api.extract_from_response(response, attribute)
        self.assertEqual(expected, output)

    def test_get_gets_response(self):
        ip, port, username, password, node_id, context = self.make_context()
        api = RECSAPI(ip, port, username, password)
        command = factory.make_string()
        params = [factory.make_string() for _ in range(3)]
        expected = dedent(
            """
            <node health="OK" id="RCU_84055620466592_BB_1_0" state="0" />
        """
        )
        response = StringIO(expected)
        self.patch(urllib.request, "urlopen", Mock(return_value=response))
        output = api.get(command, params)
        self.assertEqual(output, expected)

    def test_get_crashes_on_http_error(self):
        ip, port, username, password, node_id, context = self.make_context()
        api = RECSAPI(ip, port, username, password)
        command = factory.make_string()
        mock_urlopen = self.patch(urllib.request, "urlopen")
        mock_urlopen.side_effect = urllib.error.HTTPError(
            None, None, None, None, None
        )
        self.assertRaises(PowerConnError, api.get, command, context)

    def test_get_crashes_on_url_error(self):
        ip, port, username, password, node_id, context = self.make_context()
        api = RECSAPI(ip, port, username, password)
        command = factory.make_string()
        mock_urlopen = self.patch(urllib.request, "urlopen")
        mock_urlopen.side_effect = urllib.error.URLError("URL Error")
        self.assertRaises(PowerConnError, api.get, command, context)

    def test_post_gets_response(self):
        ip, port, username, password, node_id, context = self.make_context()
        api = RECSAPI(ip, port, username, password)
        command = factory.make_string()
        params = {
            factory.make_string(): factory.make_string() for _ in range(3)
        }
        expected = dedent(
            """
            <node health="OK" id="RCU_84055620466592_BB_1_0" state="0" />
        """
        )
        response = StringIO(expected)
        self.patch(urllib.request, "urlopen", Mock(return_value=response))
        output = api.post(command, params=params)
        self.assertEqual(output, expected)

    def test_post_crashes_on_http_error(self):
        ip, port, username, password, node_id, context = self.make_context()
        api = RECSAPI(ip, port, username, password)
        command = factory.make_string()
        mock_urlopen = self.patch(urllib.request, "urlopen")
        mock_urlopen.side_effect = urllib.error.HTTPError(
            None, None, None, None, None
        )
        self.assertRaises(PowerConnError, api.post, command, context)

    def test_post_crashes_on_url_error(self):
        ip, port, username, password, node_id, context = self.make_context()
        api = RECSAPI(ip, port, username, password)
        command = factory.make_string()
        mock_urlopen = self.patch(urllib.request, "urlopen")
        mock_urlopen.side_effect = urllib.error.URLError("URL Error")
        self.assertRaises(PowerConnError, api.post, command, context)

    def test_put_gets_response(self):
        ip, port, username, password, node_id, context = self.make_context()
        api = RECSAPI(ip, port, username, password)
        command = factory.make_string()
        params = {
            factory.make_string(): factory.make_string() for _ in range(3)
        }
        expected = dedent(
            """
            <node health="OK" id="RCU_84055620466592_BB_1_0" state="0" />
        """
        )
        response = StringIO(expected)
        self.patch(urllib.request, "urlopen", Mock(return_value=response))
        output = api.put(command, params=params)
        self.assertEqual(output, expected)

    def test_put_crashes_on_http_error(self):
        ip, port, username, password, node_id, context = self.make_context()
        api = RECSAPI(ip, port, username, password)
        command = factory.make_string()
        mock_urlopen = self.patch(urllib.request, "urlopen")
        mock_urlopen.side_effect = urllib.error.HTTPError(
            None, None, None, None, None
        )
        self.assertRaises(PowerConnError, api.put, command, context)

    def test_put_crashes_on_url_error(self):
        ip, port, username, password, node_id, context = self.make_context()
        api = RECSAPI(ip, port, username, password)
        command = factory.make_string()
        mock_urlopen = self.patch(urllib.request, "urlopen")
        mock_urlopen.side_effect = urllib.error.URLError("URL Error")
        self.assertRaises(PowerConnError, api.put, command, context)

    def test_get_node_power_state_returns_state(self):
        ip, port, username, password, node_id, context = self.make_context()
        api = RECSAPI(ip, port, username, password)
        expected = dedent(
            """
            <node health="OK" id="RCU_84055620466592_BB_1_0" state="1" />
        """
        )
        response = StringIO(expected)
        self.patch(urllib.request, "urlopen", Mock(return_value=response))
        state = api.get_node_power_state("RCU_84055620466592_BB_1_0")
        self.assertEqual(state, "1")

    def test_set_boot_source_sets_device(self):
        ip, port, username, password, node_id, context = self.make_context()
        api = RECSAPI(ip, port, username, password)
        boot_source = "2"
        boot_persistent = "false"
        params = {"source": boot_source, "persistent": boot_persistent}
        mock_put = self.patch(api, "put")
        api.set_boot_source(node_id, boot_source, boot_persistent)
        mock_put.assert_called_once_with(
            f"node/{node_id}/manage/set_bootsource", params=params
        )

    def test_set_boot_source_recs_calls_set_boot_source(self):
        ip, port, username, password, node_id, context = self.make_context()
        recs_power_driver = RECSPowerDriver()
        mock_set_boot_source = self.patch(RECSAPI, "set_boot_source")
        boot_source = "HDD"
        boot_persistent = "false"
        recs_power_driver.set_boot_source_recs(
            ip, port, username, password, node_id, boot_source, boot_persistent
        )
        mock_set_boot_source.assert_called_once_with(
            node_id, boot_source, boot_persistent
        )

    def test_get_nodes_gets_nodes(self):
        ip, port, username, password, node_id, context = self.make_context()
        api = RECSAPI(ip, port, username, password)
        response = dedent(
            """
            <nodeList>
                <node architecture="x86" baseBoardId="RCU_84055620466592_BB_1"
                 health="OK" id="RCU_84055620466592_BB_1_0"
                 ipAddressMgmt="169.254.94.58"
                 macAddressMgmt="02:00:4c:4f:4f:50"
                 subnetMaskMgmt="255.255.0.0"
                />
                <node architecture="x86" baseBoardId="RCU_84055620466592_BB_2"
                 health="OK" id="RCU_84055620466592_BB_2_0"
                 ipAddressCompute="169.254.94.59"
                 macAddressCompute="02:00:4c:4f:4f:51"
                 subnetMaskCompute="255.255.0.0"
                />
                <node architecture="arm" baseBoardId="RCU_84055620466592_BB_3"
                 health="OK" id="RCU_84055620466592_BB_3_2"
                 ipAddressMgmt="169.254.94.60"
                 macAddressMgmt="02:00:4c:4f:4f:52"
                 subnetMaskMgmt="255.255.0.0"
                 ipAddressCompute="169.254.94.61"
                 macAddressCompute="02:00:4c:4f:4f:53"
                 subnetMaskCompute="255.255.0.0"
                />
                <node architecture="x86" baseBoardId="RCU_84055620466592_BB_4"
                 health="OK" id="RCU_84055620466592_BB_4_0"
                />
            </nodeList>
        """
        )
        mock_get = self.patch(api, "get", Mock(return_value=response))
        expected = {
            "RCU_84055620466592_BB_1_0": {
                "macs": ["02:00:4c:4f:4f:50"],
                "arch": "x86",
            },
            "RCU_84055620466592_BB_2_0": {
                "macs": ["02:00:4c:4f:4f:51"],
                "arch": "x86",
            },
            "RCU_84055620466592_BB_3_2": {
                "macs": ["02:00:4c:4f:4f:52", "02:00:4c:4f:4f:53"],
                "arch": "arm",
            },
        }
        output = api.get_nodes()

        self.assertEqual(output, expected)
        mock_get.assert_called_once_with("node")

    def test_power_on_powers_on_node(self):
        ip, port, username, password, node_id, context = self.make_context()
        api = RECSAPI(ip, port, username, password)
        mock_post = self.patch(api, "post")
        api.set_power_on_node(node_id)
        mock_post.assert_called_once_with(f"node/{node_id}/manage/power_on")

    def test_power_off_powers_off_node(self):
        ip, port, username, password, node_id, context = self.make_context()
        api = RECSAPI(ip, port, username, password)
        mock_post = self.patch(api, "post")
        api.set_power_off_node(node_id)
        mock_post.assert_called_once_with(f"node/{node_id}/manage/power_off")

    def test_power_state_recs_calls_get_node_power_state_on(self):
        ip, port, username, password, node_id, context = self.make_context()
        recs_power_driver = RECSPowerDriver()
        mock_get_node_power_state = self.patch(
            RECSAPI, "get_node_power_state", Mock(return_value="1")
        )
        state = recs_power_driver.power_state_recs(
            ip, port, username, password, node_id
        )
        mock_get_node_power_state.assert_called_once_with(node_id)
        self.assertEqual("on", state)

    def test_power_state_recs_calls_get_node_power_state_off(self):
        ip, port, username, password, node_id, context = self.make_context()
        recs_power_driver = RECSPowerDriver()
        mock_get_node_power_state = self.patch(
            RECSAPI, "get_node_power_state", Mock(return_value="0")
        )
        state = recs_power_driver.power_state_recs(
            ip, port, username, password, node_id
        )
        mock_get_node_power_state.assert_called_once_with(node_id)
        self.assertEqual("off", state)

    def test_power_state_recs_crashes_on_http_error(self):
        ip, port, username, password, node_id, context = self.make_context()
        recs_power_driver = RECSPowerDriver()
        mock_get_node_power_state = self.patch(
            RECSAPI, "get_node_power_state", Mock(return_value="0")
        )
        mock_get_node_power_state.side_effect = urllib.error.HTTPError(
            None, None, None, None, None
        )
        self.assertRaises(
            RECSError,
            recs_power_driver.power_state_recs,
            ip,
            port,
            username,
            password,
            node_id,
        )

    def test_power_state_recs_crashes_on_url_error(self):
        ip, port, username, password, node_id, context = self.make_context()
        recs_power_driver = RECSPowerDriver()
        mock_get_node_power_state = self.patch(
            RECSAPI, "get_node_power_state", Mock(return_value="0")
        )
        mock_get_node_power_state.side_effect = urllib.error.URLError(
            "URL Error"
        )
        self.assertRaises(
            RECSError,
            recs_power_driver.power_state_recs,
            ip,
            port,
            username,
            password,
            node_id,
        )

    def test_power_control_recs_calls_set_power(self):
        ip, port, username, password, node_id, context = self.make_context()
        recs_power_driver = RECSPowerDriver()
        mock_set_power = self.patch(RECSAPI, "_set_power")
        recs_power_driver.power_control_recs(
            ip, port, username, password, node_id, "on"
        )
        recs_power_driver.power_control_recs(
            ip, port, username, password, node_id, "off"
        )
        mock_set_power.assert_has_calls(
            [call(node_id, "power_on"), call(node_id, "power_off")]
        )

    def test_power_control_recs_crashes_on_invalid_action(self):
        ip, port, username, password, node_id, context = self.make_context()
        recs_power_driver = RECSPowerDriver()
        self.assertRaises(
            RECSError,
            recs_power_driver.power_control_recs,
            ip,
            port,
            username,
            password,
            node_id,
            factory.make_name("action"),
        )

    @inlineCallbacks
    def test_probe_and_enlist_recs_probes_and_enlists(self):
        user = factory.make_name("user")
        ip, port, username, password, node_id, context = self.make_context()
        domain = factory.make_name("domain")
        macs = [factory.make_mac_address() for _ in range(3)]
        mock_get_nodes = self.patch(RECSAPI, "get_nodes")
        mock_get_nodes.return_value = {
            node_id: {"macs": macs, "arch": "amd64"}
        }
        self.patch(RECSAPI, "set_boot_source")
        mock_create_node = self.patch(recs_module, "create_node")
        mock_create_node.side_effect = asynchronous(lambda *args: node_id)
        mock_commission_node = self.patch(recs_module, "commission_node")

        yield deferToThread(
            probe_and_enlist_recs,
            user,
            ip,
            int(port),
            username,
            password,
            True,
            domain,
        )

        mock_create_node.assert_called_once_with(
            macs, "amd64", "recs_box", context, domain
        ),
        mock_commission_node.assert_called_once_with(node_id, user)

    @inlineCallbacks
    def test_probe_and_enlist_recs_probes_and_enlists_no_commission(self):
        user = factory.make_name("user")
        ip, port, username, password, node_id, context = self.make_context()
        domain = factory.make_name("domain")
        macs = [factory.make_mac_address() for _ in range(3)]
        mock_get_nodes = self.patch(RECSAPI, "get_nodes")
        mock_get_nodes.return_value = {node_id: {"macs": macs, "arch": "arm"}}
        self.patch(RECSAPI, "set_boot_source")
        mock_create_node = self.patch(recs_module, "create_node")
        mock_create_node.side_effect = asynchronous(lambda *args: node_id)
        mock_commission_node = self.patch(recs_module, "commission_node")

        yield deferToThread(
            probe_and_enlist_recs,
            user,
            ip,
            int(port),
            username,
            password,
            False,
            domain,
        )

        mock_create_node.assert_called_once_with(
            macs, "armhf", "recs_box", context, domain
        ),
        mock_commission_node.assert_not_called()

    @inlineCallbacks
    def test_probe_and_enlist_recs_get_nodes_failure_http_error(self):
        user = factory.make_name("user")
        ip, port, username, password, node_id, context = self.make_context()
        domain = factory.make_name("domain")
        mock_get_nodes = self.patch(RECSAPI, "get_nodes")
        mock_get_nodes.side_effect = urllib.error.HTTPError(
            None, None, None, None, None
        )

        with self.assertRaisesRegex(
            RECSError,
            r"^Failed to probe nodes for RECS_Master.*HTTP error code: None$",
        ):
            yield deferToThread(
                probe_and_enlist_recs,
                user,
                ip,
                int(port),
                username,
                password,
                True,
                domain,
            )

    @inlineCallbacks
    def test_probe_and_enlist_recs_get_nodes_failure_url_error(self):
        user = factory.make_name("user")
        ip, port, username, password, node_id, context = self.make_context()
        domain = factory.make_name("domain")
        mock_get_nodes = self.patch(RECSAPI, "get_nodes")
        mock_get_nodes.side_effect = urllib.error.URLError("URL Error")

        with self.assertRaisesRegex(
            RECSError,
            r"^Failed to probe nodes for RECS_Master.*Server could not be reached: URL Error$",
        ):
            yield deferToThread(
                probe_and_enlist_recs,
                user,
                ip,
                int(port),
                username,
                password,
                True,
                domain,
            )
