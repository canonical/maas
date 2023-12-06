# Copyright 2021 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `provisioningserver.drivers.power.proxmox`."""
import json
import random
from unittest.mock import ANY, call

from twisted.internet.defer import inlineCallbacks, succeed

from maastesting import get_testing_timeout
from maastesting.factory import factory
from maastesting.testcase import MAASTestCase, MAASTwistedRunTest
from provisioningserver.drivers.power import PowerActionError
import provisioningserver.drivers.power.proxmox as proxmox_module
from provisioningserver.drivers.power.webhook import SSL_INSECURE_NO

TIMEOUT = get_testing_timeout()


class TestProxmoxPowerDriver(MAASTestCase):
    run_tests_with = MAASTwistedRunTest.make_factory(timeout=TIMEOUT)

    def setUp(self):
        super().setUp()
        self.proxmox = proxmox_module.ProxmoxPowerDriver()
        self.mock_webhook_request = self.patch(
            self.proxmox, "_webhook_request"
        )

    def test_get_url(self):
        power_address = factory.make_name("power_address")
        endpoint = factory.make_name("endpoint")
        self.assertEqual(
            f"https://{power_address}:8006/api2/json/{endpoint}".encode(),
            self.proxmox._get_url({"power_address": power_address}, endpoint),
        )

    def test_get_url_params(self):
        power_address = factory.make_name("power_address")
        endpoint = factory.make_name("endpoint")
        params = {
            factory.make_name("key"): factory.make_name("value")
            for _ in range(3)
        }
        params_str = "&".join(
            [f"{key}={value}" for key, value in params.items()]
        )
        self.assertEqual(
            f"https://{power_address}:8006/api2/json/{endpoint}?{params_str}".encode(),
            self.proxmox._get_url(
                {"power_address": power_address}, endpoint, params
            ),
        )

    def test_get_url_funky_params(self):
        power_address = factory.make_name("power_address")
        endpoint = factory.make_name("endpoint")
        params = {"test": "? /"}
        params_str = "test=%3F+%2F"
        self.assertEqual(
            f"https://{power_address}:8006/api2/json/{endpoint}?{params_str}".encode(),
            self.proxmox._get_url(
                {"power_address": power_address}, endpoint, params
            ),
        )

    def test_get_url_allows_custom_port(self):
        power_address = "%s:443" % factory.make_name("power_address")
        endpoint = factory.make_name("endpoint")
        self.assertEqual(
            f"https://{power_address}/api2/json/{endpoint}".encode(),
            self.proxmox._get_url({"power_address": power_address}, endpoint),
        )

    @inlineCallbacks
    def test_login(self):
        system_id = factory.make_name("system_id")
        context = {
            "power_address": factory.make_name("power_address"),
            "power_user": factory.make_name("power_user"),
            "power_pass": factory.make_name("power_pass"),
        }
        ticket = factory.make_name("ticket")
        token = factory.make_name("token")
        self.mock_webhook_request.return_value = succeed(
            json.dumps(
                {
                    "data": {
                        "ticket": ticket,
                        "CSRFPreventionToken": token,
                    }
                }
            )
        )

        extra_headers = yield self.proxmox._login(system_id, context)

        self.assertEqual(
            {
                b"Cookie": [f"PVEAuthCookie={ticket}".encode()],
                b"CSRFPreventionToken": [token.encode()],
            },
            extra_headers,
        )
        self.mock_webhook_request.assert_called_once_with(
            b"POST",
            self.proxmox._get_url(context, "access/ticket"),
            self.proxmox._make_auth_headers(
                system_id,
                {},
                {b"Content-Type": [b"application/json; charset=utf-8"]},
            ),
            False,
            # unittest doesn't know how to compare FileBodyProducer
            ANY,
        )

    @inlineCallbacks
    def test_login_uses_api_token(self):
        system_id = factory.make_name("system_id")
        power_user = factory.make_name("power_user")
        context = {
            "power_address": factory.make_name("power_address"),
            "power_user": power_user,
            "power_pass": factory.make_name("power_pass"),
            "power_token_name": f"{power_user}!{factory.make_name('power_token_name')}",
            "power_token_secret": factory.make_name("power_token_secret"),
        }

        extra_headers = yield self.proxmox._login(system_id, context)

        self.assertEqual(
            {
                b"Authorization": [
                    f"PVEAPIToken={context['power_token_name']}="
                    f"{context['power_token_secret']}".encode()
                ]
            },
            extra_headers,
        )
        self.mock_webhook_request.assert_not_called()

    @inlineCallbacks
    def test_login_uses_api_token_adds_username(self):
        system_id = factory.make_name("system_id")
        context = {
            "power_address": factory.make_name("power_address"),
            "power_user": factory.make_name("power_user"),
            "power_pass": factory.make_name("power_pass"),
            "power_token_name": factory.make_name("power_token_name"),
            "power_token_secret": factory.make_name("power_token_secret"),
        }

        extra_headers = yield self.proxmox._login(system_id, context)

        self.assertEqual(
            {
                b"Authorization": [
                    f"PVEAPIToken={context['power_user']}!"
                    f"{context['power_token_name']}="
                    f"{context['power_token_secret']}".encode()
                ]
            },
            extra_headers,
        )
        self.mock_webhook_request.assert_not_called()

    @inlineCallbacks
    def test_find_vm(self):
        system_id = factory.make_name("system_id")
        context = {
            "power_address": factory.make_name("power_address"),
            "power_vm_name": factory.make_name("power_vm_name"),
        }
        vm = {random.choice(["vmid", "name"]): context["power_vm_name"]}
        extra_headers = {
            factory.make_name("key").encode(): [
                factory.make_name("value").encode()
            ]
            for _ in range(3)
        }
        self.mock_webhook_request.return_value = succeed(
            json.dumps({"data": [vm]})
        )

        found_vm = yield self.proxmox._find_vm(
            system_id, context, extra_headers
        )

        self.assertEqual(vm, found_vm)
        self.mock_webhook_request.assert_called_once_with(
            b"GET",
            self.proxmox._get_url(
                context, "cluster/resources", {"type": "vm"}
            ),
            self.proxmox._make_auth_headers(system_id, {}, extra_headers),
            False,
        )

    @inlineCallbacks
    def test_find_vm_doesnt_find_any_vms(self):
        system_id = factory.make_name("system_id")
        context = {
            "power_address": factory.make_name("power_address"),
            "power_vm_name": factory.make_name("power_vm_name"),
        }
        extra_headers = {
            factory.make_name("key").encode(): [
                factory.make_name("value").encode()
            ]
            for _ in range(3)
        }
        self.mock_webhook_request.return_value = succeed(
            json.dumps({"data": []})
        )

        with self.assertRaisesRegex(
            PowerActionError, "No VMs returned! Are permissions set correctly?"
        ):
            yield self.proxmox._find_vm(system_id, context, extra_headers)
        self.mock_webhook_request.assert_called_once_with(
            b"GET",
            self.proxmox._get_url(
                context, "cluster/resources", {"type": "vm"}
            ),
            self.proxmox._make_auth_headers(system_id, {}, extra_headers),
            False,
        )

    @inlineCallbacks
    def test_find_vm_doesnt_find_vm(self):
        system_id = factory.make_name("system_id")
        context = {
            "power_address": factory.make_name("power_address"),
            "power_vm_name": factory.make_name("power_vm_name"),
        }
        vm = {
            random.choice(["vmid", "name"]): factory.make_name(
                "another_power_vm_name"
            )
        }
        extra_headers = {
            factory.make_name("key").encode(): [
                factory.make_name("value").encode()
            ]
            for _ in range(3)
        }
        self.mock_webhook_request.return_value = succeed(
            json.dumps({"data": [vm]})
        )

        with self.assertRaisesRegex(
            PowerActionError, "Unable to find virtual machine"
        ):
            yield self.proxmox._find_vm(system_id, context, extra_headers)
        self.mock_webhook_request.assert_called_once_with(
            b"GET",
            self.proxmox._get_url(
                context, "cluster/resources", {"type": "vm"}
            ),
            self.proxmox._make_auth_headers(system_id, {}, extra_headers),
            False,
        )

    @inlineCallbacks
    def test_power_on(self):
        system_id = factory.make_name("system_id")
        context = {"power_address": factory.make_name("power_address")}
        extra_headers = {
            factory.make_name("key").encode(): [
                factory.make_name("value").encode()
            ]
            for _ in range(3)
        }
        vm = {
            "node": factory.make_name("node"),
            "type": factory.make_name("type"),
            "vmid": factory.make_name("vmid"),
            "status": "stopped",
        }
        self.patch(self.proxmox, "_login").return_value = succeed(
            extra_headers
        )
        self.patch(self.proxmox, "_find_vm").return_value = succeed(vm)

        yield self.proxmox.power_on(system_id, context)

        self.mock_webhook_request.assert_called_once_with(
            b"POST",
            self.proxmox._get_url(
                context,
                f"nodes/{vm['node']}/{vm['type']}/{vm['vmid']}/"
                "status/start",
            ),
            self.proxmox._make_auth_headers(system_id, {}, extra_headers),
            False,
        )

    @inlineCallbacks
    def test_power_on_not_called_if_on(self):
        system_id = factory.make_name("system_id")
        context = {"power_address": factory.make_name("power_address")}
        extra_headers = {
            factory.make_name("key").encode(): [
                factory.make_name("value").encode()
            ]
            for _ in range(3)
        }
        vm = {
            "node": factory.make_name("node"),
            "type": factory.make_name("type"),
            "vmid": factory.make_name("vmid"),
            "status": "running",
        }
        self.patch(self.proxmox, "_login").return_value = succeed(
            extra_headers
        )
        self.patch(self.proxmox, "_find_vm").return_value = succeed(vm)

        yield self.proxmox.power_on(system_id, context)

        self.mock_webhook_request.assert_not_called()

    @inlineCallbacks
    def test_power_off(self):
        system_id = factory.make_name("system_id")
        context = {"power_address": factory.make_name("power_address")}
        extra_headers = {
            factory.make_name("key").encode(): [
                factory.make_name("value").encode()
            ]
            for _ in range(3)
        }
        vm = {
            "node": factory.make_name("node"),
            "type": factory.make_name("type"),
            "vmid": factory.make_name("vmid"),
            "status": "running",
        }
        self.patch(self.proxmox, "_login").return_value = succeed(
            extra_headers
        )
        self.patch(self.proxmox, "_find_vm").return_value = succeed(vm)

        yield self.proxmox.power_off(system_id, context)

        self.mock_webhook_request.assert_called_once_with(
            b"POST",
            self.proxmox._get_url(
                context,
                f"nodes/{vm['node']}/{vm['type']}/{vm['vmid']}/" "status/stop",
            ),
            self.proxmox._make_auth_headers(system_id, {}, extra_headers),
            False,
        )

    @inlineCallbacks
    def test_power_off_not_called_if_off(self):
        system_id = factory.make_name("system_id")
        context = {"power_address": factory.make_name("power_address")}
        extra_headers = {
            factory.make_name("key").encode(): [
                factory.make_name("value").encode()
            ]
            for _ in range(3)
        }
        vm = {
            "node": factory.make_name("node"),
            "type": factory.make_name("type"),
            "vmid": factory.make_name("vmid"),
            "status": "stopped",
        }
        self.patch(self.proxmox, "_login").return_value = succeed(
            extra_headers
        )
        self.patch(self.proxmox, "_find_vm").return_value = succeed(vm)

        yield self.proxmox.power_off(system_id, context)

        self.mock_webhook_request.assert_not_called()

    @inlineCallbacks
    def test_power_query_on(self):
        system_id = factory.make_name("system_id")
        context = {"power_address": factory.make_name("power_address")}
        extra_headers = {
            factory.make_name("key").encode(): [
                factory.make_name("value").encode()
            ]
            for _ in range(3)
        }
        vm = {
            "node": factory.make_name("node"),
            "type": factory.make_name("type"),
            "vmid": factory.make_name("vmid"),
            "status": "running",
        }
        self.patch(self.proxmox, "_login").return_value = succeed(
            extra_headers
        )
        self.patch(self.proxmox, "_find_vm").return_value = succeed(vm)

        status = yield self.proxmox.power_query(system_id, context)

        self.assertEqual("on", status)

    @inlineCallbacks
    def test_power_query_off(self):
        system_id = factory.make_name("system_id")
        context = {"power_address": factory.make_name("power_address")}
        extra_headers = {
            factory.make_name("key").encode(): [
                factory.make_name("value").encode()
            ]
            for _ in range(3)
        }
        vm = {
            "node": factory.make_name("node"),
            "type": factory.make_name("type"),
            "vmid": factory.make_name("vmid"),
            "status": "stopped",
        }
        self.patch(self.proxmox, "_login").return_value = succeed(
            extra_headers
        )
        self.patch(self.proxmox, "_find_vm").return_value = succeed(vm)

        status = yield self.proxmox.power_query(system_id, context)

        self.assertEqual("off", status)

    @inlineCallbacks
    def test_power_query_unknown(self):
        system_id = factory.make_name("system_id")
        context = {"power_address": factory.make_name("power_address")}
        extra_headers = {
            factory.make_name("key").encode(): [
                factory.make_name("value").encode()
            ]
            for _ in range(3)
        }
        vm = {
            "node": factory.make_name("node"),
            "type": factory.make_name("type"),
            "vmid": factory.make_name("vmid"),
            "status": factory.make_name("status"),
        }
        self.patch(self.proxmox, "_login").return_value = succeed(
            extra_headers
        )
        self.patch(self.proxmox, "_find_vm").return_value = succeed(vm)

        status = yield self.proxmox.power_query(system_id, context)

        self.assertEqual("unknown", status)


class TestProxmoxProbeAndEnlist(MAASTestCase):
    run_tests_with = MAASTwistedRunTest.make_factory(timeout=TIMEOUT)

    def setUp(self):
        super().setUp()
        self.mock_login = self.patch(
            proxmox_module.ProxmoxPowerDriver, "_login"
        )
        self.mock_login.return_value = succeed({})
        self.system_id = factory.make_name("system_id")
        self.mock_create_node = self.patch(proxmox_module, "create_node")
        self.mock_create_node.return_value = succeed(self.system_id)
        self.mock_commission_node = self.patch(
            proxmox_module, "commission_node"
        )
        self.mock_commission_node.return_value = succeed(None)

    @inlineCallbacks
    def test_probe_and_enlist(self):
        user = factory.make_name("user")
        hostname = factory.make_ipv4_address()
        username = factory.make_name("username")
        password = factory.make_name("password")
        token_name = factory.make_name("token_name")
        token_secret = factory.make_name("token_secret")
        domain = factory.make_name("domain")
        node1 = factory.make_name("node1")
        vmid1 = random.randint(0, 100)
        mac11 = factory.make_mac_address()
        mac12 = factory.make_mac_address()
        node2 = factory.make_name("node2")
        vmid2 = random.randint(0, 100)
        mac21 = factory.make_mac_address()
        mac22 = factory.make_mac_address()
        mock_webhook_request = self.patch(
            proxmox_module.ProxmoxPowerDriver, "_webhook_request"
        )
        mock_webhook_request.side_effect = [
            succeed(
                json.dumps(
                    {
                        "data": [
                            {
                                "node": node1,
                                "vmid": vmid1,
                                "name": f"vm {vmid1}",
                                "type": "qemu",
                                "status": "stopped",
                            },
                            {
                                "node": node2,
                                "vmid": vmid2,
                                "name": f"vm {vmid2}",
                                "type": "qemu",
                                "status": "stopped",
                            },
                        ]
                    }
                ).encode()
            ),
            succeed(
                b"{'data': {"
                b"'net1':'virtio=%s,bridge=vmbr0,firewall=1'"
                b"'net2':'virtio=%s,bridge=vmbr0,firewall=1'"
                b"}}" % (mac11.encode(), mac12.encode())
            ),
            succeed(
                b"{'data': {"
                b"'net1':'virtio=%s,bridge=vmbr0,firewall=1'"
                b"'net2':'virtio=%s,bridge=vmbr0,firewall=1'"
                b"}}" % (mac21.encode(), mac22.encode())
            ),
        ]

        yield proxmox_module.probe_proxmox_and_enlist(
            user,
            hostname,
            username,
            password,
            token_name,
            token_secret,
            False,
            False,
            domain,
            None,
        )

        self.mock_create_node.assert_has_calls(
            [
                call(
                    [mac11, mac12],
                    "amd64",
                    "proxmox",
                    {
                        "power_vm_name": vmid1,
                        "power_address": hostname,
                        "power_user": username,
                        "power_pass": password,
                        "power_token_name": token_name,
                        "power_token_secret": token_secret,
                        "power_verify_ssl": SSL_INSECURE_NO,
                    },
                    domain,
                    hostname=f"vm-{vmid1}",
                ),
                call(
                    [mac21, mac22],
                    "amd64",
                    "proxmox",
                    {
                        "power_vm_name": vmid2,
                        "power_address": hostname,
                        "power_user": username,
                        "power_pass": password,
                        "power_token_name": token_name,
                        "power_token_secret": token_secret,
                        "power_verify_ssl": SSL_INSECURE_NO,
                    },
                    domain,
                    hostname=f"vm-{vmid2}",
                ),
            ]
        )
        self.mock_commission_node.assert_not_called()

    @inlineCallbacks
    def test_probe_and_enlist_doesnt_find_any_vms(self):
        user = factory.make_name("user")
        hostname = factory.make_ipv4_address()
        username = factory.make_name("username")
        password = factory.make_name("password")
        token_name = factory.make_name("token_name")
        token_secret = factory.make_name("token_secret")
        domain = factory.make_name("domain")
        mock_webhook_request = self.patch(
            proxmox_module.ProxmoxPowerDriver, "_webhook_request"
        )
        mock_webhook_request.return_value = succeed(json.dumps({"data": []}))

        with self.assertRaisesRegex(
            PowerActionError, "No VMs returned! Are permissions set correctly?"
        ):
            yield proxmox_module.probe_proxmox_and_enlist(
                user,
                hostname,
                username,
                password,
                token_name,
                token_secret,
                False,
                False,
                domain,
                None,
            )

    @inlineCallbacks
    def test_probe_and_enlist_filters(self):
        user = factory.make_name("user")
        hostname = factory.make_ipv4_address()
        username = factory.make_name("username")
        password = factory.make_name("password")
        token_name = factory.make_name("token_name")
        token_secret = factory.make_name("token_secret")
        domain = factory.make_name("domain")
        node1 = factory.make_name("node1")
        mac11 = factory.make_mac_address()
        mac12 = factory.make_mac_address()
        node2 = factory.make_name("node2")
        mac21 = factory.make_mac_address()
        mac22 = factory.make_mac_address()
        mock_webhook_request = self.patch(
            proxmox_module.ProxmoxPowerDriver, "_webhook_request"
        )
        mock_webhook_request.side_effect = [
            succeed(
                json.dumps(
                    {
                        "data": [
                            {
                                "node": node1,
                                "vmid": 100,
                                "name": "vm 100",
                                "type": "qemu",
                                "status": "stopped",
                            },
                            {
                                "node": node2,
                                "vmid": 200,
                                "name": "vm 200",
                                "type": "qemu",
                                "status": "stopped",
                            },
                        ]
                    }
                ).encode()
            ),
            succeed(
                b"{'data': {"
                b"'net1':'virtio=%s,bridge=vmbr0,firewall=1'"
                b"'net2':'virtio=%s,bridge=vmbr0,firewall=1'"
                b"}}" % (mac11.encode(), mac12.encode())
            ),
            succeed(
                b"{'data': {"
                b"'net1':'virtio=%s,bridge=vmbr0,firewall=1'"
                b"'net2':'virtio=%s,bridge=vmbr0,firewall=1'"
                b"}}" % (mac21.encode(), mac22.encode())
            ),
        ]

        yield proxmox_module.probe_proxmox_and_enlist(
            user,
            hostname,
            username,
            password,
            token_name,
            token_secret,
            False,
            False,
            domain,
            "vm 1",
        )

        self.mock_create_node.assert_called_once_with(
            [mac11, mac12],
            "amd64",
            "proxmox",
            {
                "power_vm_name": 100,
                "power_address": hostname,
                "power_user": username,
                "power_pass": password,
                "power_token_name": token_name,
                "power_token_secret": token_secret,
                "power_verify_ssl": SSL_INSECURE_NO,
            },
            domain,
            hostname="vm-100",
        )

        self.mock_commission_node.assert_not_called()

    @inlineCallbacks
    def test_probe_and_enlist_stops_and_commissions(self):
        user = factory.make_name("user")
        hostname = factory.make_ipv4_address()
        username = factory.make_name("username")
        password = factory.make_name("password")
        token_name = factory.make_name("token_name")
        token_secret = factory.make_name("token_secret")
        domain = factory.make_name("domain")
        node1 = factory.make_name("node1")
        vmid1 = random.randint(0, 100)
        mac11 = factory.make_mac_address()
        mac12 = factory.make_mac_address()
        mock_webhook_request = self.patch(
            proxmox_module.ProxmoxPowerDriver, "_webhook_request"
        )
        mock_webhook_request.side_effect = [
            succeed(
                json.dumps(
                    {
                        "data": [
                            {
                                "node": node1,
                                "vmid": vmid1,
                                "name": f"vm {vmid1}",
                                "type": "qemu",
                                "status": "running",
                            },
                        ]
                    }
                ).encode()
            ),
            succeed(
                b"{'data': {"
                b"'net1':'virtio=%s,bridge=vmbr0,firewall=1'"
                b"'net2':'virtio=%s,bridge=vmbr0,firewall=1'"
                b"}}" % (mac11.encode(), mac12.encode())
            ),
            succeed(None),
        ]

        yield proxmox_module.probe_proxmox_and_enlist(
            user,
            hostname,
            username,
            password,
            token_name,
            token_secret,
            False,
            True,
            domain,
            None,
        )

        self.mock_create_node.assert_called_once_with(
            [mac11, mac12],
            "amd64",
            "proxmox",
            {
                "power_vm_name": vmid1,
                "power_address": hostname,
                "power_user": username,
                "power_pass": password,
                "power_token_name": token_name,
                "power_token_secret": token_secret,
                "power_verify_ssl": SSL_INSECURE_NO,
            },
            domain,
            hostname=f"vm-{vmid1}",
        )
        mock_webhook_request.assert_called_with(b"POST", ANY, ANY, False)
        self.mock_commission_node.assert_called_once_with(self.system_id, user)

    @inlineCallbacks
    def test_probe_and_enlist_ignores_create_node_error(self):
        user = factory.make_name("user")
        hostname = factory.make_ipv4_address()
        username = factory.make_name("username")
        password = factory.make_name("password")
        token_name = factory.make_name("token_name")
        token_secret = factory.make_name("token_secret")
        domain = factory.make_name("domain")
        node1 = factory.make_name("node1")
        vmid1 = random.randint(0, 100)
        mac11 = factory.make_mac_address()
        mac12 = factory.make_mac_address()
        self.mock_create_node.return_value = succeed(None)
        mock_webhook_request = self.patch(
            proxmox_module.ProxmoxPowerDriver, "_webhook_request"
        )
        mock_webhook_request.side_effect = [
            succeed(
                json.dumps(
                    {
                        "data": [
                            {
                                "node": node1,
                                "vmid": vmid1,
                                "name": f"vm {vmid1}",
                                "type": "qemu",
                                "status": "running",
                            },
                        ]
                    }
                ).encode()
            ),
            succeed(
                b"{'data': {"
                b"'net1':'virtio=%s,bridge=vmbr0,firewall=1'"
                b"'net2':'virtio=%s,bridge=vmbr0,firewall=1'"
                b"}}" % (mac11.encode(), mac12.encode())
            ),
            succeed(None),
        ]

        yield proxmox_module.probe_proxmox_and_enlist(
            user,
            hostname,
            username,
            password,
            token_name,
            token_secret,
            False,
            True,
            domain,
            None,
        )

        self.mock_create_node.assert_called_once_with(
            [mac11, mac12],
            "amd64",
            "proxmox",
            {
                "power_vm_name": vmid1,
                "power_address": hostname,
                "power_user": username,
                "power_pass": password,
                "power_token_name": token_name,
                "power_token_secret": token_secret,
                "power_verify_ssl": SSL_INSECURE_NO,
            },
            domain,
            hostname=f"vm-{vmid1}",
        )
        self.mock_commission_node.assert_not_called()
