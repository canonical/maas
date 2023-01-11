# Copyright 2021 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Generic Proxmox Power Driver."""

from io import BytesIO
import json
from urllib.parse import urlencode, urlparse

from twisted.internet.defer import inlineCallbacks, succeed
from twisted.web.client import FileBodyProducer

from provisioningserver.drivers import (
    IP_EXTRACTOR_PATTERNS,
    make_ip_extractor,
    make_setting_field,
    SETTING_SCOPE,
)
from provisioningserver.drivers.power import PowerActionError
from provisioningserver.drivers.power.webhook import (
    SSL_INSECURE_CHOICES,
    SSL_INSECURE_NO,
    WebhookPowerDriver,
)
from provisioningserver.utils.twisted import asynchronous


class ProxmoxPowerDriver(WebhookPowerDriver):

    name = "proxmox"
    chassis = False
    # XXX ltrager - 2021-01-11 - Support for probing and Pods could be added.
    can_probe = False
    description = "Proxmox"
    settings = [
        make_setting_field(
            "power_address", "Proxmox host name or IP", required=True
        ),
        make_setting_field(
            "power_user", "Proxmox username, including realm", required=True
        ),
        make_setting_field(
            "power_pass",
            "Proxmox password, required if a token name and secret aren't "
            "given",
            field_type="password",
        ),
        make_setting_field("power_token_name", "Proxmox API token name"),
        make_setting_field(
            "power_token_secret",
            "Proxmox API token secret",
            field_type="password",
        ),
        make_setting_field(
            "power_vm_name", "Node ID", scope=SETTING_SCOPE.NODE
        ),
        make_setting_field(
            "power_verify_ssl",
            "Verify SSL connections with system CA certificates",
            field_type="choice",
            required=True,
            choices=SSL_INSECURE_CHOICES,
            default=SSL_INSECURE_NO,
        ),
    ]

    ip_extractor = make_ip_extractor(
        "power_address", IP_EXTRACTOR_PATTERNS.URL
    )

    def _get_url(self, context, endpoint, params=None):
        url = urlparse(context["power_address"])
        if not url.scheme:
            # When the scheme is not included in the power address
            # urlparse puts the url into path.
            url = url._replace(scheme="https", netloc=url.path, path="")
        if not url.port:
            if url.netloc:
                url = url._replace(netloc="%s:8006" % url.netloc)
            else:
                # Similar to above, we need to swap netloc and path.
                url = url._replace(netloc="%s:8006" % url.path, path="")
        if params:
            query = urlencode(params)
        else:
            query = ""
        url = url._replace(
            path="/api2/json/%s" % endpoint, query=query, fragment=""
        )
        return url.geturl().encode()

    def _login(self, system_id, context):
        power_token_name = context.get("power_token_name")
        if power_token_name:
            if "!" not in power_token_name:
                # The username must be included with the token name. Proxmox
                # docs doesn't make this obvious and the UI includes it.
                power_token_name = (
                    f"{context['power_user']}!{power_token_name}"
                )
            return succeed(
                {
                    b"Authorization": [
                        f"PVEAPIToken={power_token_name}="
                        f"{context['power_token_secret']}".encode()
                    ]
                }
            )

        d = self._webhook_request(
            b"POST",
            self._get_url(context, "access/ticket"),
            # Proxmox doesn't support basic HTTP authentication. Don't pass
            # the context so an authorization header isn't created.
            self._make_auth_headers(
                system_id,
                {},
                {b"Content-Type": [b"application/json; charset=utf-8"]},
            ),
            context.get("power_verify_ssl") is True,
            FileBodyProducer(
                BytesIO(
                    json.dumps(
                        {
                            "username": context["power_user"],
                            "password": context["power_pass"],
                        }
                    ).encode()
                )
            ),
        )

        def cb(response_data):
            parsed_data = json.loads(response_data)
            return {
                b"Cookie": [
                    f"PVEAuthCookie={parsed_data['data']['ticket']}".encode()
                ],
                b"CSRFPreventionToken": [
                    parsed_data["data"]["CSRFPreventionToken"].encode()
                ],
            }

        d.addCallback(cb)
        return d

    def _find_vm(self, system_id, context, extra_headers):
        power_vm_name = context["power_vm_name"]
        d = self._webhook_request(
            b"GET",
            self._get_url(context, "cluster/resources", {"type": "vm"}),
            self._make_auth_headers(system_id, {}, extra_headers),
            context.get("power_verify_ssl") is True,
        )

        def cb(response_data):
            parsed_data = json.loads(response_data)
            for vm in parsed_data["data"]:
                if power_vm_name in (str(vm.get("vmid")), vm.get("name")):
                    return vm
            raise PowerActionError("Unable to find virtual machine")

        d.addCallback(cb)
        return d

    @asynchronous
    @inlineCallbacks
    def power_on(self, system_id, context):
        extra_headers = yield self._login(system_id, context)
        vm = yield self._find_vm(system_id, context, extra_headers)
        if vm["status"] != "running":
            yield self._webhook_request(
                b"POST",
                self._get_url(
                    context,
                    f"nodes/{vm['node']}/{vm['type']}/{vm['vmid']}/"
                    "status/start",
                ),
                self._make_auth_headers(system_id, {}, extra_headers),
                context.get("power_verify_ssl") is True,
            )

    @asynchronous
    @inlineCallbacks
    def power_off(self, system_id, context):
        extra_headers = yield self._login(system_id, context)
        vm = yield self._find_vm(system_id, context, extra_headers)
        if vm["status"] != "stopped":
            yield self._webhook_request(
                b"POST",
                self._get_url(
                    context,
                    f"nodes/{vm['node']}/{vm['type']}/{vm['vmid']}/"
                    "status/stop",
                ),
                self._make_auth_headers(system_id, {}, extra_headers),
                context.get("power_verify_ssl") is True,
            )

    @asynchronous
    @inlineCallbacks
    def power_query(self, system_id, context):
        extra_headers = yield self._login(system_id, context)
        vm = yield self._find_vm(system_id, context, extra_headers)
        if vm["status"] == "running":
            return "on"
        elif vm["status"] == "stopped":
            return "off"
        else:
            return "unknown"
