# Copyright 2021 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `provisioningserver.drivers.power.proxmox`."""
import json
import random
from unittest.mock import ANY

from testtools import ExpectedException
from twisted.internet.defer import inlineCallbacks, succeed

from maastesting.factory import factory
from maastesting.matchers import MockCalledOnceWith, MockNotCalled
from maastesting.testcase import MAASTestCase, MAASTwistedRunTest
from provisioningserver.drivers.power import PowerActionError
import provisioningserver.drivers.power.proxmox as proxmox_module


class TestProxmoxPowerDriver(MAASTestCase):

    run_tests_with = MAASTwistedRunTest.make_factory(timeout=5)

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
        self.assertThat(
            self.mock_webhook_request,
            MockCalledOnceWith(
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
            ),
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
        self.assertThat(self.mock_webhook_request, MockNotCalled())

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
        self.assertThat(self.mock_webhook_request, MockNotCalled())

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
        self.assertThat(
            self.mock_webhook_request,
            MockCalledOnceWith(
                b"GET",
                self.proxmox._get_url(
                    context, "cluster/resources", {"type": "vm"}
                ),
                self.proxmox._make_auth_headers(system_id, {}, extra_headers),
                False,
            ),
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

        with ExpectedException(PowerActionError):
            yield self.proxmox._find_vm(system_id, context, extra_headers)
        self.assertThat(
            self.mock_webhook_request,
            MockCalledOnceWith(
                b"GET",
                self.proxmox._get_url(
                    context, "cluster/resources", {"type": "vm"}
                ),
                self.proxmox._make_auth_headers(system_id, {}, extra_headers),
                False,
            ),
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

        self.assertThat(
            self.mock_webhook_request,
            MockCalledOnceWith(
                b"POST",
                self.proxmox._get_url(
                    context,
                    f"nodes/{vm['node']}/{vm['type']}/{vm['vmid']}/"
                    "status/start",
                ),
                self.proxmox._make_auth_headers(system_id, {}, extra_headers),
                False,
            ),
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

        self.assertThat(self.mock_webhook_request, MockNotCalled())

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

        self.assertThat(
            self.mock_webhook_request,
            MockCalledOnceWith(
                b"POST",
                self.proxmox._get_url(
                    context,
                    f"nodes/{vm['node']}/{vm['type']}/{vm['vmid']}/"
                    "status/stop",
                ),
                self.proxmox._make_auth_headers(system_id, {}, extra_headers),
                False,
            ),
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

        self.assertThat(self.mock_webhook_request, MockNotCalled())

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
