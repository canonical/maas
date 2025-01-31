# Copyright 2021-2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Generic Webhook Power Driver."""

import base64
from http import HTTPStatus
import re

from twisted.internet import reactor
from twisted.internet.defer import inlineCallbacks
from twisted.web.client import (
    Agent,
    PartialDownloadError,
    readBody,
    RedirectAgent,
)
from twisted.web.http_headers import Headers

from provisioningserver.drivers import (
    IP_EXTRACTOR_PATTERNS,
    make_ip_extractor,
    make_setting_field,
)
from provisioningserver.drivers.power import PowerActionError, PowerDriver
from provisioningserver.drivers.power.utils import WebClientContextFactory
from provisioningserver.utils.twisted import asynchronous
from provisioningserver.utils.version import get_running_version

SSL_INSECURE_YES = "y"
SSL_INSECURE_NO = "n"

SSL_INSECURE_CHOICES = [[SSL_INSECURE_NO, "No"], [SSL_INSECURE_YES, "Yes"]]


class WebhookPowerDriver(PowerDriver):
    name = "webhook"
    chassis = False
    can_probe = False
    can_set_boot_order = False
    description = "Webhook"
    settings = [
        make_setting_field(
            "power_on_uri", "URI to power on the node", required=True
        ),
        make_setting_field(
            "power_off_uri", "URI to power off the node", required=True
        ),
        make_setting_field(
            "power_query_uri",
            "URI to query the nodes power status",
            required=True,
        ),
        make_setting_field(
            "power_on_regex",
            "Regex to confirm the node is on",
            default=r"status.*\:.*running",
            required=True,
        ),
        make_setting_field(
            "power_off_regex",
            "Regex to confirm the node is off",
            default=r"status.*\:.*stopped",
            required=True,
        ),
        make_setting_field("power_user", "Power user"),
        make_setting_field(
            "power_pass", "Power password", field_type="password", secret=True
        ),
        make_setting_field(
            "power_token",
            "Power token, will be used in place of power_user and power_pass",
            field_type="password",
            secret=True,
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

    # Use the power_query_uri as that is the URL MAAS uses the most.
    ip_extractor = make_ip_extractor(
        "power_query_uri", IP_EXTRACTOR_PATTERNS.URL
    )

    def _make_auth_headers(self, system_id, context, extra_headers=None):
        """Return authentication headers."""
        power_user = context.get("power_user")
        power_pass = context.get("power_pass")
        power_token = context.get("power_token")
        if extra_headers is None:
            extra_headers = {}

        # Don't include a Content-Type here, some services will reject the
        # request unless content is expected.
        headers = {
            b"User-Agent": [f"MAAS {get_running_version()}".encode()],
            b"Accept": [b"application/json"],
            **extra_headers,
        }

        if system_id:
            headers[b"System_Id"] = [system_id.encode()]

        if power_token:
            headers[b"Authorization"] = [f"Bearer {power_token}".encode()]
        elif power_user and power_pass:
            # Base64 encoded per RFC7617
            headers[b"Authorization"] = [
                b"Basic "
                + base64.b64encode(f"{power_user}:{power_pass}".encode())
            ]
        return Headers(headers)

    def _webhook_request(
        self, method, uri, headers, verify_ssl=False, bodyProducer=None
    ):
        """Send the webhook request and return the response."""

        agent = RedirectAgent(
            Agent(
                reactor,
                contextFactory=WebClientContextFactory(verify=verify_ssl),
            )
        )
        d = agent.request(
            method,
            uri,
            headers=headers,
            bodyProducer=bodyProducer,
        )

        def render_response(response):
            """Render the HTTPS response received."""

            def eb_catch_partial(failure):
                # Twisted is raising PartialDownloadError because the responses
                # do not contain a Content-Length header. Since every response
                # holds the whole body we just take the result.
                failure.trap(PartialDownloadError)
                if int(failure.value.status) == HTTPStatus.OK:
                    return failure.value.response
                else:
                    return failure

            # Error out if the response has a status code of 400 or above.
            if response.code >= int(HTTPStatus.BAD_REQUEST):
                # if there was no trailing slash, retry with a trailing slash
                # because of varying requirements of BMC manufacturers
                if response.code == HTTPStatus.NOT_FOUND and uri[-1] != b"/":
                    d = agent.request(
                        method,
                        uri + b"/",
                        headers=headers,
                        bodyProducer=bodyProducer,
                    )
                else:
                    raise PowerActionError(
                        f"Request failed with response status code: {response.code}."
                    )

            d = readBody(response)
            d.addErrback(eb_catch_partial)
            return d

        d.addCallback(render_response)
        return d

    def detect_missing_packages(self):
        # uses Twisted http client - nothing to look for!
        return []

    @asynchronous
    @inlineCallbacks
    def power_on(self, system_id, context):
        """Power on webhook."""
        yield self._webhook_request(
            b"POST",
            context["power_on_uri"].encode(),
            self._make_auth_headers(system_id, context),
            context.get("power_verify_ssl") == SSL_INSECURE_YES,
        )

    @asynchronous
    @inlineCallbacks
    def power_off(self, system_id, context):
        """Power off webhook."""
        yield self._webhook_request(
            b"POST",
            context["power_off_uri"].encode(),
            self._make_auth_headers(system_id, context),
            context.get("power_verify_ssl") == SSL_INSECURE_YES,
        )

    @asynchronous
    @inlineCallbacks
    def power_query(self, system_id, context):
        """Power query webhook."""
        power_on_regex = context.get("power_on_regex")
        power_off_regex = context.get("power_off_regex")

        node_data = yield self._webhook_request(
            b"GET",
            context["power_query_uri"].encode(),
            self._make_auth_headers(system_id, context),
            context.get("power_verify_ssl") == SSL_INSECURE_YES,
        )
        node_data = node_data.decode()
        if power_on_regex and re.search(power_on_regex, node_data) is not None:
            return "on"
        elif (
            power_off_regex
            and re.search(power_off_regex, node_data) is not None
        ):
            return "off"
        else:
            return "unknown"

    @asynchronous
    @inlineCallbacks
    def power_reset(self, system_id, context):
        """Power reset webhook."""
        raise NotImplementedError()
