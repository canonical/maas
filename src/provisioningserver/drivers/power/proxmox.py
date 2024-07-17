# Copyright 2021 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Generic Proxmox Power Driver."""

from io import BytesIO
import json
import re
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
    SSL_INSECURE_YES,
    WebhookPowerDriver,
)
from provisioningserver.rpc.utils import commission_node, create_node
from provisioningserver.utils.twisted import asynchronous


class ProxmoxPowerDriver(WebhookPowerDriver):
    name = "proxmox"
    chassis = True
    can_probe = True
    can_set_boot_order = False
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
            secret=True,
        ),
        make_setting_field("power_token_name", "Proxmox API token name"),
        make_setting_field(
            "power_token_secret",
            "Proxmox API token secret",
            field_type="password",
            secret=True,
        ),
        make_setting_field(
            "power_vm_name", "Node ID", scope=SETTING_SCOPE.NODE, required=True
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
            context.get("power_verify_ssl") == SSL_INSECURE_YES,
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
            context.get("power_verify_ssl") == SSL_INSECURE_YES,
        )

        def cb(response_data):
            parsed_data = json.loads(response_data)
            vms = parsed_data["data"]
            if not vms:
                raise PowerActionError(
                    "No VMs returned! Are permissions set correctly?"
                )
            for vm in vms:
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
                context.get("power_verify_ssl") == SSL_INSECURE_YES,
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
                context.get("power_verify_ssl") == SSL_INSECURE_YES,
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


def probe_proxmox_and_enlist(
    user,
    hostname,
    username,
    password,
    token_name,
    token_secret,
    verify_ssl,
    accept_all,
    domain,
    prefix_filter,
):
    """Extracts all of the VMs from Proxmox and enlists them into MAAS.

    :param user: user for the nodes.
    :param hostname: Hostname for Proxmox
    :param username: The username to connect to Proxmox to
    :param password: The password to connect to Proxmox with.
    :param token_name: The name of the token to use instead of a password.
    :param token_secret: The token secret to use instead of a password.
    :param verify_ssl: Whether SSL connections should be verified.
    :param accept_all: If True, commission enlisted nodes.
    :param domain: What domain discovered machines to be apart of.
    :param prefix_filter: only enlist nodes that have the prefix.
    """
    proxmox = ProxmoxPowerDriver()
    context = {
        "power_address": hostname,
        "power_user": username,
        "power_pass": password,
        "power_token_name": token_name,
        "power_token_secret": token_secret,
        "power_verify_ssl": (
            SSL_INSECURE_YES if verify_ssl else SSL_INSECURE_NO
        ),
    }
    mac_regex = re.compile(r"(([\dA-F]{2}[:]){5}[\dA-F]{2})", re.I)

    d = proxmox._login("", context)

    @inlineCallbacks
    def get_vms(extra_headers):
        vms = yield proxmox._webhook_request(
            b"GET",
            proxmox._get_url(context, "cluster/resources", {"type": "vm"}),
            proxmox._make_auth_headers("", {}, extra_headers),
            verify_ssl,
        )
        return extra_headers, vms

    d.addCallback(get_vms)

    @inlineCallbacks
    def process_vms(data):
        extra_headers, response_data = data
        vms = json.loads(response_data)["data"]
        if not vms:
            raise PowerActionError(
                "No VMs returned! Are permissions set correctly?"
            )
        for vm in vms:
            if prefix_filter and not vm["name"].startswith(prefix_filter):
                continue
            # Proxmox doesn't have an easy way to get the MAC address, it
            # includes it with a bunch of other data in the config.
            vm_config_data = yield proxmox._webhook_request(
                b"GET",
                proxmox._get_url(
                    context,
                    f"nodes/{vm['node']}/{vm['type']}/{vm['vmid']}/config",
                ),
                proxmox._make_auth_headers("", {}, extra_headers),
                verify_ssl,
            )
            macs = [
                mac[0] for mac in mac_regex.findall(vm_config_data.decode())
            ]

            system_id = yield create_node(
                macs,
                "amd64",
                "proxmox",
                {"power_vm_name": vm["vmid"], **context},
                domain,
                hostname=vm["name"].replace(" ", "-"),
            )

            # If the system_id is None an error occured when creating the machine.
            # Most likely the error is the node already exists.
            if system_id is None:
                continue

            if vm["status"] != "stopped":
                yield proxmox._webhook_request(
                    b"POST",
                    proxmox._get_url(
                        context,
                        f"nodes/{vm['node']}/{vm['type']}/{vm['vmid']}/"
                        "status/stop",
                    ),
                    proxmox._make_auth_headers(system_id, {}, extra_headers),
                    context.get("power_verify_ssl") == SSL_INSECURE_YES,
                )

            if accept_all:
                yield commission_node(system_id, user)

    d.addCallback(process_vms)
    return d
