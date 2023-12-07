# Copyright 2014-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from io import StringIO
from itertools import permutations
import random
from unittest.mock import ANY, call, Mock, sentinel
import urllib.error
import urllib.parse
import urllib.request

from lxml.etree import Element, SubElement, XML
from twisted.internet.defer import inlineCallbacks
from twisted.internet.threads import deferToThread

from maastesting import get_testing_timeout
from maastesting.factory import factory
from maastesting.testcase import MAASTestCase, MAASTwistedRunTest
from provisioningserver.drivers.hardware import ucsm
from provisioningserver.drivers.hardware.ucsm import (
    get_children,
    get_first_booter,
    get_macs,
    get_power_command,
    get_server_power_control,
    get_servers,
    get_service_profile,
    logged_in,
    make_policy_change,
    make_request_data,
    parse_response,
    power_control_ucsm,
    power_state_ucsm,
    probe_and_enlist_ucsm,
    probe_lan_boot_options,
    probe_servers,
    RO_KEYS,
    set_lan_boot_default,
    set_server_power_control,
    strip_ro_keys,
    UCSM_XML_API,
    UCSM_XML_API_Error,
)
from provisioningserver.utils.twisted import asynchronous


def make_api(
    url="http://url", user="u", password="p", cookie="foo", mock_call=True
):
    api = UCSM_XML_API(url, user, password)
    api.cookie = cookie
    return api


def make_api_patch_call(testcase, *args, **kwargs):
    api = make_api(*args, **kwargs)
    mock = testcase.patch(api, "_call")
    return api, mock


def make_fake_result(root_class, child_tag, container="outConfigs"):
    fake_result = Element(root_class)
    outConfigs = SubElement(fake_result, container)
    outConfigs.append(Element(child_tag))
    return outConfigs


def make_class():
    return factory.make_name("class")


def make_dn():
    return factory.make_name("dn")


def make_server(power_state=None):
    return {"operPower": power_state}


class TestUCSMXMLAPIError(MAASTestCase):
    def test_includes_code_and_msg(self):
        def raise_error():
            raise UCSM_XML_API_Error("bad", 4224)

        error = self.assertRaises(UCSM_XML_API_Error, raise_error)

        self.assertEqual("bad", error.args[0])
        self.assertEqual(4224, error.code)


class TestMakeRequestData(MAASTestCase):
    def test_no_children(self):
        fields = {"hello": "there"}
        request_data = make_request_data("foo", fields)
        root = XML(request_data)
        self.assertEqual("foo", root.tag)
        self.assertEqual("there", root.get("hello"))

    def test_with_children(self):
        fields = {"hello": "there"}
        children_tags = ["bar", "baz"]
        children = [Element(child_tag) for child_tag in children_tags]
        request_data = make_request_data("foo", fields, children)
        root = XML(request_data)
        self.assertEqual("foo", root.tag)
        self.assertEqual(children_tags, [e.tag for e in root])

    def test_no_fields(self):
        request_data = make_request_data("foo")
        root = XML(request_data)
        self.assertEqual("foo", root.tag)


class TestParseResonse(MAASTestCase):
    def test_no_error(self):
        xml = "<foo/>"
        response = parse_response(xml)
        self.assertEqual("foo", response.tag)

    def test_error(self):
        xml = '<foo errorCode="123" errorDescr="mayday!"/>'
        self.assertRaises(UCSM_XML_API_Error, parse_response, xml)


class TestLogin(MAASTestCase):
    def test_login_assigns_cookie(self):
        cookie = "chocolate chip"
        api, mock = make_api_patch_call(self)
        mock.return_value = Element("aaaLogin", {"outCookie": cookie})
        api.login()
        self.assertEqual(cookie, api.cookie)

    def test_login_call_parameters(self):
        user = "user"
        password = "pass"
        api, mock = make_api_patch_call(self, user=user, password=password)
        api.login()
        fields = {"inName": user, "inPassword": password}
        mock.assert_called_once_with("aaaLogin", fields)


class TestLogout(MAASTestCase):
    def test_logout_clears_cookie(self):
        api = make_api()
        self.patch(api, "_call")
        api.logout()
        self.assertIsNone(api.cookie)

    def test_logout_uses_cookie(self):
        api, mock = make_api_patch_call(self)
        cookie = api.cookie
        api.logout()
        fields = {"inCookie": cookie}
        mock.assert_called_once_with("aaaLogout", fields)


class TestConfigResolveClass(MAASTestCase):
    def test_no_filters(self):
        class_id = make_class()
        api, mock = make_api_patch_call(self)
        api.config_resolve_class(class_id)
        fields = {"cookie": api.cookie, "classId": class_id}
        mock.assert_called_once_with("configResolveClass", fields, ANY)

    def test_with_filters(self):
        class_id = make_class()
        filter_element = Element("hi")
        api, mock = make_api_patch_call(self)
        api.config_resolve_class(class_id, [filter_element])
        in_filters = mock.call_args[0][2]
        self.assertEqual([filter_element], in_filters[0][:])

    def test_return_response(self):
        api, mock = make_api_patch_call(self)
        mock.return_value = Element("test")
        result = api.config_resolve_class("c")
        self.assertEqual(mock.return_value, result)


class TestConfigResolveChildren(MAASTestCase):
    def test_parameters(self):
        dn = make_dn()
        class_id = make_class()
        api, mock = make_api_patch_call(self)
        api.config_resolve_children(dn, class_id)
        fields = {"inDn": dn, "classId": class_id, "cookie": api.cookie}
        mock.assert_called_once_with("configResolveChildren", fields)

    def test_no_class_id(self):
        dn = make_dn()
        api, mock = make_api_patch_call(self)
        api.config_resolve_children(dn)
        fields = {"inDn": dn, "cookie": api.cookie}
        mock.assert_called_once_with("configResolveChildren", fields)

    def test_return_response(self):
        api, mock = make_api_patch_call(self)
        mock.return_value = Element("test")
        result = api.config_resolve_children("d", "c")
        self.assertEqual(mock.return_value, result)


class TestConfigConfMo(MAASTestCase):
    def test_parameters(self):
        dn = make_dn()
        config_items = [Element("hi")]
        api, mock = make_api_patch_call(self)
        api.config_conf_mo(dn, config_items)
        fields = {"dn": dn, "cookie": api.cookie}
        mock.assert_called_once_with("configConfMo", fields, ANY)
        in_configs = mock.call_args[0][2]
        self.assertEqual(config_items, in_configs[0][:])


class TestCall(MAASTestCase):
    def test_call(self):
        name = "method"
        fields = {1: 2}
        children = [3, 4]
        request = "<yes/>"
        response = Element("good")
        api = make_api()

        mock_make_request_data = self.patch(ucsm, "make_request_data")
        mock_make_request_data.return_value = request

        mock_send_request = self.patch(api, "_send_request")
        mock_send_request.return_value = response

        api._call(name, fields, children)
        mock_make_request_data.assert_called_once_with(name, fields, children)
        mock_send_request.assert_called_once_with(request)


class TestSendRequest(MAASTestCase):
    def test_send_request(self):
        request_data = "foo"
        api = make_api()
        self.patch(api, "_call")
        stream = StringIO("<hi/>")
        mock = self.patch(urllib.request, "urlopen")
        mock.return_value = stream
        response = api._send_request(request_data)
        self.assertEqual("hi", response.tag)
        urllib_request = mock.call_args[0][0]
        self.assertEqual(request_data, urllib_request.data)


class TestConfigResolveDn(MAASTestCase):
    def test_parameters(self):
        api, mock = make_api_patch_call(self)
        test_dn = make_dn()
        fields = {"cookie": api.cookie, "dn": test_dn}
        api.config_resolve_dn(test_dn)
        mock.assert_called_once_with("configResolveDn", fields)


class TestGetServers(MAASTestCase):
    def test_uses_uuid(self):
        uuid = factory.make_UUID()
        api = make_api()
        mock = self.patch(api, "config_resolve_class")
        get_servers(api, uuid)
        filters = mock.call_args[0][1]
        attrib = {"class": "computeItem", "property": "uuid", "value": uuid}
        self.assertEqual(attrib, filters[0].attrib)

    def test_returns_result(self):
        uuid = factory.make_UUID()
        api = make_api()
        fake_result = make_fake_result("configResolveClass", "found")
        self.patch(api, "config_resolve_class").return_value = fake_result
        result = get_servers(api, uuid)
        self.assertEqual("found", result[0].tag)

    def test_class_id(self):
        uuid = factory.make_UUID()
        api = make_api()
        mock = self.patch(api, "config_resolve_class")
        get_servers(api, uuid)
        mock.assert_called_once_with("computeItem", ANY)


class TestProbeLanBootOptions(MAASTestCase):
    def test_returns_result(self):
        api = make_api()
        server = sentinel.server
        mock_service_profile = Mock()
        mock_get_service_profile = self.patch(ucsm, "get_service_profile")
        mock_get_service_profile.return_value = mock_service_profile
        mock_service_profile.get.return_value = sentinel.profile_get
        fake_result = make_fake_result("tag", "lsbootLan")
        mock_config_resolve_children = self.patch(
            api, "config_resolve_children"
        )
        mock_config_resolve_children.return_value = fake_result
        self.assertEqual(1, len(probe_lan_boot_options(api, server)))
        mock_config_resolve_children.assert_called_once_with(
            sentinel.profile_get
        )
        mock_service_profile.get.assert_called_once_with("operBootPolicyName")
        mock_get_service_profile.assert_called_once_with(api, server)


class TestGetChildren(MAASTestCase):
    def test_returns_result(self):
        search_class = make_class()
        api = make_api()
        fake_result = make_fake_result("configResolveChildren", search_class)
        self.patch(api, "config_resolve_children").return_value = fake_result
        in_element = Element("test", {"dn": make_dn()})
        class_id = search_class
        result = get_children(api, in_element, class_id)
        self.assertEqual(search_class, result[0].tag)

    def test_parameters(self):
        search_class = make_class()
        parent_dn = make_dn()
        api = make_api()
        mock = self.patch(api, "config_resolve_children")
        in_element = Element("test", {"dn": parent_dn})
        class_id = search_class
        get_children(api, in_element, class_id)
        mock.assert_called_once_with(parent_dn, search_class)


class TestGetMacs(MAASTestCase):
    def test_gets_adaptors(self):
        adaptor = "adaptor"
        server = make_server()
        mac = "xx"
        api = make_api()
        mock = self.patch(ucsm, "get_children")

        def fake_get_children(api, element, class_id):
            if class_id == "adaptorUnit":
                return [adaptor]
            elif class_id == "adaptorHostEthIf":
                return [Element("ethif", {"mac": mac})]

        mock.side_effect = fake_get_children
        macs = get_macs(api, server)
        mock.assert_has_calls(
            [
                call(api, server, "adaptorUnit"),
                call(api, adaptor, "adaptorHostEthIf"),
            ]
        )
        self.assertEqual([mac], macs)


class TestProbeServers(MAASTestCase):
    def test_uses_api(self):
        api = make_api()
        mock = self.patch(ucsm, "get_servers")
        probe_servers(api)
        mock.assert_called_once_with(api)

    def test_returns_results(self):
        servers = [{"uuid": factory.make_UUID()}]
        mac = "mac"
        api = make_api()
        self.patch(ucsm, "get_servers").return_value = servers
        self.patch(ucsm, "get_macs").return_value = [mac]
        self.patch(ucsm, "probe_lan_boot_options").return_value = ["option"]
        server_list = probe_servers(api)
        self.assertEqual([(servers[0], [mac])], server_list)

    def test_no_results_with_no_server_macs(self):
        servers = [{"uuid": factory.make_UUID()}]
        api = make_api()
        self.patch(ucsm, "get_servers").return_value = servers
        self.patch(ucsm, "get_macs").return_value = []
        self.patch(ucsm, "probe_lan_boot_options").return_value = ["option"]
        server_list = probe_servers(api)
        self.assertEqual([], server_list)

    def test_no_results_with_no_boot_options(self):
        servers = [{"uuid": factory.make_UUID()}]
        mac = "mac"
        api = make_api()
        self.patch(ucsm, "get_servers").return_value = servers
        self.patch(ucsm, "get_macs").return_value = mac
        self.patch(ucsm, "probe_lan_boot_options").return_value = []
        server_list = probe_servers(api)
        self.assertEqual([], server_list)


class TestGetServerPowerControl(MAASTestCase):
    def test_get_server_power_control(self):
        api = make_api()
        mock = self.patch(api, "config_resolve_children")
        fake_result = make_fake_result("configResolveChildren", "lsPower")
        mock.return_value = fake_result
        dn = make_dn()
        server = Element("computeItem", {"assignedToDn": dn})
        power_control = get_server_power_control(api, server)
        mock.assert_called_once_with(dn, "lsPower")
        self.assertEqual("lsPower", power_control.tag)


class TestSetServerPowerControl(MAASTestCase):
    def test_set_server_power_control(self):
        api = make_api()
        power_dn = make_dn()
        power_control = Element("lsPower", {"dn": power_dn})
        config_conf_mo_mock = self.patch(api, "config_conf_mo")
        state = "state"
        set_server_power_control(api, power_control, state)
        config_conf_mo_mock.assert_called_once_with(power_dn, ANY)
        power_change = config_conf_mo_mock.call_args[0][1][0]
        self.assertEqual(power_change.tag, "lsPower")
        self.assertEqual({"state": state, "dn": power_dn}, power_change.attrib)


class TestLoggedIn(MAASTestCase):
    def test_logged_in(self):
        mock = self.patch(ucsm, "UCSM_XML_API")
        url = "url"
        username = "username"
        password = "password"
        mock.return_value = Mock()

        with logged_in(url, username, password) as api:
            self.assertEqual(mock.return_value, api)
            api.login()

        mock.return_value.logout.assert_called_once_with()


class TestValidGetPowerCommand(MAASTestCase):
    scenarios = [
        (
            "Power On",
            dict(power_mode="on", current_state="down", command="admin-up"),
        ),
        (
            "Power On",
            dict(
                power_mode="on", current_state="up", command="cycle-immediate"
            ),
        ),
        (
            "Power Off",
            dict(power_mode="off", current_state="up", command="admin-down"),
        ),
    ]

    def test_get_power_command(self):
        command = get_power_command(self.power_mode, self.current_state)
        self.assertEqual(self.command, command)


class TestInvalidGetPowerCommand(MAASTestCase):
    def test_get_power_command_raises_assertion_error_on_bad_power_mode(self):
        bad_power_mode = factory.make_name("unlikely")
        error = self.assertRaises(
            UCSM_XML_API_Error, get_power_command, bad_power_mode, None
        )
        self.assertIn(bad_power_mode, error.args[0])


class TestPowerControlUCSM(MAASTestCase):
    def test_power_control_ucsm(self):
        uuid = factory.make_UUID()
        api = Mock()
        self.patch(ucsm, "UCSM_XML_API").return_value = api
        get_servers_mock = self.patch(ucsm, "get_servers")
        server = make_server()
        state = "admin-down"
        power_control = Element("lsPower", {"state": state})
        get_servers_mock.return_value = [server]
        get_server_power_control_mock = self.patch(
            ucsm, "get_server_power_control"
        )
        get_server_power_control_mock.return_value = power_control
        set_server_power_control_mock = self.patch(
            ucsm, "set_server_power_control"
        )
        power_control_ucsm("url", "username", "password", uuid, "off")
        get_servers_mock.assert_called_once_with(api, uuid)
        set_server_power_control_mock.assert_called_once_with(
            api, power_control, state
        )


class TestUCSMPowerState(MAASTestCase):
    def test_power_state_get_off(self):
        url = factory.make_name("url")
        username = factory.make_name("username")
        password = factory.make_name("password")
        uuid = factory.make_UUID()
        api = Mock()
        self.patch(ucsm, "UCSM_XML_API").return_value = api
        get_servers_mock = self.patch(ucsm, "get_servers")
        get_servers_mock.return_value = [make_server("off")]

        power_state = power_state_ucsm(url, username, password, uuid)
        get_servers_mock.assert_called_once_with(api, uuid)
        self.assertEqual(power_state, "off")

    def test_power_state_get_on(self):
        url = factory.make_name("url")
        username = factory.make_name("username")
        password = factory.make_name("password")
        uuid = factory.make_UUID()
        api = Mock()
        self.patch(ucsm, "UCSM_XML_API").return_value = api
        get_servers_mock = self.patch(ucsm, "get_servers")
        get_servers_mock.return_value = [make_server("on")]

        power_state = power_state_ucsm(url, username, password, uuid)
        get_servers_mock.assert_called_once_with(api, uuid)
        self.assertEqual(power_state, "on")

    def test_power_state_error_on_unknown_state(self):
        url = factory.make_name("url")
        username = factory.make_name("username")
        password = factory.make_name("password")
        uuid = factory.make_UUID()
        api = Mock()
        self.patch(ucsm, "UCSM_XML_API").return_value = api
        get_servers_mock = self.patch(ucsm, "get_servers")
        get_servers_mock.return_value = [make_server()]

        self.assertRaises(
            UCSM_XML_API_Error, power_state_ucsm, url, username, password, uuid
        )


class TestProbeAndEnlistUCSM(MAASTestCase):
    run_tests_with = MAASTwistedRunTest.make_factory(
        timeout=get_testing_timeout()
    )

    @inlineCallbacks
    def test_probe_and_enlist(self):
        user = factory.make_name("user")
        url = factory.make_name("url")
        username = factory.make_name("username")
        password = factory.make_name("password")
        system_id = factory.make_name("system_id")
        domain = factory.make_name("domain")
        api = Mock()
        self.patch(ucsm, "UCSM_XML_API").return_value = api
        server_element = {"uuid": "uuid"}
        server = (server_element, ["mac"])
        probe_servers_mock = self.patch(ucsm, "probe_servers")
        probe_servers_mock.return_value = [server]
        set_lan_boot_default_mock = self.patch(ucsm, "set_lan_boot_default")
        create_node_mock = self.patch(ucsm, "create_node")
        create_node_mock.side_effect = asynchronous(lambda *args: system_id)
        commission_node_mock = self.patch(ucsm, "commission_node")

        yield deferToThread(
            probe_and_enlist_ucsm, user, url, username, password, True, domain
        )
        set_lan_boot_default_mock.assert_called_once_with(api, server_element)
        probe_servers_mock.assert_called_once_with(api)
        params = {
            "power_address": url,
            "power_user": username,
            "power_pass": password,
            "uuid": server[0]["uuid"],
        }
        create_node_mock.assert_called_once_with(
            server[1], "amd64", "ucsm", params, domain
        )
        commission_node_mock.assert_called_once_with(system_id, user)


class TestGetServiceProfile(MAASTestCase):
    def test_get_service_profile(self):
        test_dn = make_dn()
        server = Element("computeBlade", {"assignedToDn": test_dn})
        api = make_api()
        mock = self.patch(api, "config_resolve_dn")
        mock.return_value = make_fake_result(
            "configResolveDn", "lsServer", "outConfig"
        )
        service_profile = get_service_profile(api, server)
        mock.assert_called_once_with(test_dn)
        self.assertEqual(mock.return_value[0], service_profile)


def make_boot_order_scenarios(size):
    """Produce test scenarios for testing get_first_booter.

    Each scenario is one of the permutations of a set of ``size``
    elements, where each element has an integer 'order' attribute
    that get_first_booter will use to determine which device boots
    first.
    """
    minimum = random.randint(0, 500)
    ordinals = range(minimum, minimum + size)

    elements = [Element("Entry%d" % i, {"order": "%d" % i}) for i in ordinals]

    orders = permutations(elements)
    orders = [{"order": order} for order in orders]

    scenarios = [("%d" % i, order) for i, order in enumerate(orders)]
    return scenarios, minimum


class TestGetFirstBooter(MAASTestCase):
    scenarios, minimum = make_boot_order_scenarios(3)

    def test_first_booter(self):
        """Ensure the boot device is picked according to the order
        attribute, not the order of elements in the list of devices."""
        root = Element("outConfigs")
        root.extend(self.order)
        picked = get_first_booter(root)
        self.assertEqual(self.minimum, int(picked.get("order")))


class TestsForStripRoKeys(MAASTestCase):
    def test_strip_ro_keys(self):
        attributes = {key: "DC" for key in RO_KEYS}

        elements = [
            Element(f"Element{i}", attributes)
            for i in range(random.randint(0, 10))
        ]

        strip_ro_keys(elements)

        for key in RO_KEYS:
            values = [element.get(key) for element in elements]
            for value in values:
                self.assertIsNone(value)


class TestMakePolicyChange(MAASTestCase):
    def test_lan_already_top_priority(self):
        boot_profile_response = make_fake_result(
            "configResolveChildren", "lsbootLan"
        )
        mock = self.patch(ucsm, "get_first_booter")
        mock.return_value = boot_profile_response[0]
        change = make_policy_change(boot_profile_response)
        self.assertIsNone(change)
        mock.assert_called_once_with(boot_profile_response)

    def test_change_lan_to_top_priority(self):
        boot_profile_response = Element("outConfigs")
        lan_boot = Element("lsbootLan", {"order": "second"})
        storage_boot = Element("lsbootStorage", {"order": "first"})
        boot_profile_response.extend([lan_boot, storage_boot])
        self.patch(ucsm, "get_first_booter").return_value = storage_boot
        self.patch(ucsm, "strip_ro_keys")
        change = make_policy_change(boot_profile_response)
        lan_boot_order = change.xpath("//lsbootPolicy/lsbootLan/@order")
        storage_boot_order = change.xpath(
            "//lsbootPolicy/lsbootStorage/@order"
        )
        self.assertEqual(["first"], lan_boot_order)
        self.assertEqual(["second"], storage_boot_order)


class TestSetLanBootDefault(MAASTestCase):
    def test_no_change(self):
        api = make_api()
        server = make_server()
        self.patch(ucsm, "get_service_profile")
        self.patch(api, "config_resolve_children")
        self.patch(ucsm, "make_policy_change").return_value = None
        config_conf_mo = self.patch(api, "config_conf_mo")
        set_lan_boot_default(api, server)
        config_conf_mo.assert_not_called()

    def test_with_change(self):
        api = make_api()
        server = make_server()
        test_dn = make_dn()
        test_change = "change"
        service_profile = Element("test", {"operBootPolicyName": test_dn})
        self.patch(ucsm, "get_service_profile").return_value = service_profile
        self.patch(api, "config_resolve_children")
        self.patch(ucsm, "make_policy_change").return_value = test_change
        config_conf_mo = self.patch(api, "config_conf_mo")
        set_lan_boot_default(api, server)
        config_conf_mo.assert_called_once_with(test_dn, [test_change])
