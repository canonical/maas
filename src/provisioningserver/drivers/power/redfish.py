# Copyright 2018-2021 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Redfish Power Driver."""


from base64 import b64encode
from enum import Enum
from http import HTTPStatus
from io import BytesIO
import json
from os.path import basename, join
from typing import Callable

from twisted.internet import reactor
from twisted.internet.defer import inlineCallbacks, succeed
from twisted.web.client import (
    Agent,
    FileBodyProducer,
    PartialDownloadError,
    readBody,
    RedirectAgent,
)
from twisted.web.http_headers import Headers

from provisioningserver.drivers import (
    make_ip_extractor,
    make_setting_field,
    SETTING_SCOPE,
)
from provisioningserver.drivers.power import PowerActionError, PowerDriver
from provisioningserver.drivers.power.utils import WebClientContextFactory
from provisioningserver.enum import POWER_STATE
from provisioningserver.logger import get_maas_logger
from provisioningserver.utils.twisted import asynchronous, pause

maaslog = get_maas_logger("drivers.power.redfish")


# no trailing slashes
REDFISH_POWER_CONTROL_ENDPOINT = (
    b"redfish/v1/Systems/%s/Actions/ComputerSystem.Reset"
)

REDFISH_SYSTEMS_ENDPOINT = b"redfish/v1/Systems"

MAX_REQUEST_RETRIES = 5

MAX_STATUS_REQUEST_RETRIES = 7


class PowerChange(str, Enum):
    OFF = "ForceOff"
    ON = "On"


class RedfishPowerDriverBase(PowerDriver):
    def get_url(self, context):
        """Return url for the pod."""
        url = context.get("power_address")
        if "https" not in url and "http" not in url:
            # Prepend https
            url = join("https://", url)
        return url.encode("utf-8")

    def make_auth_headers(self, power_user, power_pass, **kwargs):
        """Return authentication headers."""
        creds = f"{power_user}:{power_pass}"
        authorization = b64encode(creds.encode("utf-8"))
        return Headers(
            {
                b"User-Agent": [b"MAAS"],
                b"Accept": [b"application/json"],
                b"Authorization": [b"Basic " + authorization],
                b"Content-Type": [b"application/json"],
            }
        )

    @inlineCallbacks
    def redfish_request(
        self,
        method,
        uri,
        headers=None,
        get_bodyProducer: Callable = lambda: None,
        get_etag: Callable = lambda: succeed(None),
    ):
        retries = 0
        while True:
            # Exponential backoff
            sleep_time = ((2**retries) - 1) / 2
            yield pause(sleep_time)
            try:
                etag = yield get_etag()
                if etag:
                    # previous attempts might have added this header, hence we have to replace it.
                    headers.removeHeader(b"If-Match")
                    headers.addRawHeader(b"If-Match", etag)
                return (
                    yield self._redfish_request(
                        method, uri, headers, get_bodyProducer
                    )
                )
            except Exception as e:
                if retries == MAX_REQUEST_RETRIES:
                    maaslog.error(
                        "Maximum number of retries reached. Giving up!"
                    )
                    raise e
                maaslog.info(
                    "Power action failure: %s. This is the try number %d out of 6.",
                    e,
                    retries,
                )
                retries += 1

    @asynchronous
    def _redfish_request(
        self,
        method,
        uri,
        headers=None,
        get_bodyProducer: Callable = lambda: None,
    ):
        """Send the Redfish request and return the response."""
        agent = RedirectAgent(
            Agent(reactor, contextFactory=WebClientContextFactory())
        )
        d = agent.request(
            method, uri, headers=headers, bodyProducer=get_bodyProducer()
        )

        def render_response(response, uri):
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

            def cb_json_decode(data):
                data = data.decode("utf-8")
                # Only decode non-empty response bodies.
                if data:
                    # occasionally invalid json is returned. provide a clear
                    # error in that case
                    try:
                        return json.loads(data)
                    except ValueError as error:
                        raise PowerActionError(
                            "Redfish request failed from a JSON parse error:"
                            " %s." % error
                        )

            def cb_attach_headers(data, headers):
                return data, headers

            if response.code >= int(HTTPStatus.BAD_REQUEST) or (
                response.code == int(HTTPStatus.PERMANENT_REDIRECT)
            ):
                # Error out if the response has a status code of 400 or above.
                if response.code >= int(HTTPStatus.BAD_REQUEST):
                    # if there was no trailing slash,
                    # retry with a trailing slash
                    # because of varying requirements of BMC manufacturers
                    if response.code == HTTPStatus.NOT_FOUND and (
                        uri.decode("utf-8")[-1] != "/"
                    ):
                        d = agent.request(
                            method,
                            uri + b"/",
                            headers=headers,
                            bodyProducer=get_bodyProducer(),
                        )
                    else:
                        raise PowerActionError(
                            "Redfish request failed with response status code:"
                            " %s." % response.code
                        )
                elif response.code == int(HTTPStatus.PERMANENT_REDIRECT):
                    uri = response.headers.getRawHeaders(b"location")[0]
                    if b"http" in uri:
                        d = agent.request(
                            method,
                            uri,
                            headers=headers,
                            bodyProducer=get_bodyProducer(),
                        )
                    else:
                        raise PowerActionError(
                            "Redfish request failed with response status code:"
                            " %s." % response.code
                        )
                d.addCallback(readBody)
            else:
                d = readBody(response)

            d.addErrback(eb_catch_partial)
            d.addCallback(cb_json_decode)
            d.addCallback(cb_attach_headers, headers=response.headers)
            return d

        d.addCallback(render_response, uri=uri)
        return d


# XXX ltrager - 2021-01-12 - Change parent class to WebhookPowerDriver.
class RedfishPowerDriver(RedfishPowerDriverBase):
    chassis = True  # Redfish API endpoints can be probed and enlisted.
    can_probe = False
    can_set_boot_order = False

    name = "redfish"
    description = "Redfish"
    settings = [
        make_setting_field("power_address", "Redfish address", required=True),
        make_setting_field("power_user", "Redfish user", required=True),
        make_setting_field(
            "power_pass",
            "Redfish password",
            field_type="password",
            required=True,
            secret=True,
        ),
        make_setting_field("node_id", "Node ID", scope=SETTING_SCOPE.NODE),
    ]
    ip_extractor = make_ip_extractor("power_address")

    def detect_missing_packages(self):
        # no required packages
        return []

    @inlineCallbacks
    def process_redfish_context(self, context):
        """Process Redfish power driver context.

        Returns the basename of the first member found
        in the Redfish Systems:

        "Members": [
          {
            "@odata.id": "/redfish/v1/Systems/1"
          }
        """
        url = self.get_url(context)
        headers = self.make_auth_headers(**context)
        node_id = context.get("node_id")
        if node_id:
            node_id = node_id.encode("utf-8")
        else:
            node_id = yield self.get_node_id(url, headers)
        return url, node_id, headers

    @inlineCallbacks
    def get_etag(self, url, node_id, headers):
        """Get the system Etag suggested for PATCH calls"""
        uri = join(url, REDFISH_SYSTEMS_ENDPOINT, b"%s" % node_id)
        node_data, node_headers = yield self.redfish_request(
            b"GET", uri, headers
        )
        etag = node_data.get("@odata.etag")
        if etag is None and node_headers.getRawHeaders("etag"):
            etag = node_headers.getRawHeaders("etag")[0]

        if etag:
            etag = etag.encode("utf-8")
        return etag

    @inlineCallbacks
    def get_node_id(self, url, headers):
        uri = join(url, REDFISH_SYSTEMS_ENDPOINT)
        systems, _ = yield self.redfish_request(b"GET", uri, headers)
        members = systems.get("Members")
        # remove trailing slashes. basename('...Systems/1/) = ''
        member = members[0].get("@odata.id").rstrip("/")
        return basename(member).encode("utf-8")

    @inlineCallbacks
    def set_pxe_boot(self, url, node_id, headers):
        """Set the machine with node_id to PXE boot."""
        endpoint = join(REDFISH_SYSTEMS_ENDPOINT, b"%s" % node_id)

        def _get_bodyProducer():
            return FileBodyProducer(
                BytesIO(
                    json.dumps(
                        {
                            "Boot": {
                                "BootSourceOverrideEnabled": "Once",
                                "BootSourceOverrideTarget": "Pxe",
                            }
                        }
                    ).encode("utf-8")
                )
            )

        @inlineCallbacks
        def _get_etag():
            result = yield self.get_etag(url, node_id, headers)
            return result

        yield self.redfish_request(
            b"PATCH",
            join(url, endpoint),
            headers,
            _get_bodyProducer,
            _get_etag,
        )

    @inlineCallbacks
    def power(self, power_change: PowerChange, url, node_id, headers):
        """Issue `power` command."""
        endpoint = REDFISH_POWER_CONTROL_ENDPOINT % node_id

        def _get_bodyProducer():
            return FileBodyProducer(
                BytesIO(
                    json.dumps({"ResetType": power_change}).encode("utf-8")
                )
            )

        yield self.redfish_request(
            b"POST", join(url, endpoint), headers, _get_bodyProducer
        )

        # Always wait for the BMC to transition to the desired status!
        if power_change == PowerChange.OFF:
            yield self._wait_for_status(POWER_STATE.OFF, url, node_id, headers)
        if power_change == PowerChange.ON:
            yield self._wait_for_status(POWER_STATE.ON, url, node_id, headers)

    @asynchronous
    @inlineCallbacks
    def power_on(self, node_id, context):
        """Power on machine."""
        url, node_id, headers = yield self.process_redfish_context(context)
        power_state = yield self._power_query(url, node_id, headers)
        # Power off the machine if currently on.
        if power_state == POWER_STATE.ON:
            yield self.power(PowerChange.OFF, url, node_id, headers)
        # Set to PXE boot.
        yield self.set_pxe_boot(url, node_id, headers)
        # Power on the machine.
        yield self.power(PowerChange.ON, url, node_id, headers)

    @asynchronous
    @inlineCallbacks
    def power_off(self, node_id, context):
        """Power off machine."""
        url, node_id, headers = yield self.process_redfish_context(context)
        # Power off the machine if it is not already off and wait until the BMC confirms that.
        power_state = yield self._power_query(url, node_id, headers)
        if power_state != POWER_STATE.OFF:
            yield self.power(PowerChange.OFF, url, node_id, headers)
        # Set to PXE boot.
        yield self.set_pxe_boot(url, node_id, headers)

    @asynchronous
    @inlineCallbacks
    def power_query(self, system_id, context: dict) -> str:
        """Power query machine.

        According to the Redfish schema, the power states can take the following values:
            Off, On, Paused, PoweringOff, PoweringOn

        MAAS defines its own device-agnostic power states based on the definition of POWER_STATE (enum) class.
        According to POWER_STATE the next values are allowed:
            on, off, unknown, error

        power_query queries the power state of the machine and maps the response to the device-agnostic power state
        defined by MAAS. The mapping between Redfish and MAAS is as follows:
            Redfish-Off -> MAAS-OFF
            Redfish-On -> MAAS-ON
            Redfish-Paused -> MAAS-ON
            Redfish-PoweringOn -> MAAS-OFF
            Redfish-PoweringOff -> MAAS-ON

        Reference:
        https://www.dmtf.org/sites/default/files/standards/documents/DSP2046_2023.3.html#powerstate
        """
        url, node_id, headers = yield self.process_redfish_context(context)
        return (yield self._power_query(url, node_id, headers))

    @asynchronous
    @inlineCallbacks
    def _power_query(self, url, node_id, headers, retries=0) -> str:
        uri = join(url, REDFISH_SYSTEMS_ENDPOINT, b"%s" % node_id)
        node_data, _ = yield self.redfish_request(b"GET", uri, headers)
        node_power_state = node_data.get("PowerState", "Null")
        if not node_power_state:
            node_power_state = "Null"
        node_power_state = node_power_state.lower()
        match node_power_state:
            case "off" | "poweringon":
                return POWER_STATE.OFF
            case "on" | "paused" | "poweringoff":
                return POWER_STATE.ON
            case "reset" | "unknown" | "null":
                # HPE Gen11 and above might return also Reset, Unknown or Null. Since they are transitional statuses,
                # we have to wait until we get a known one.
                if retries == MAX_STATUS_REQUEST_RETRIES:
                    maaslog.error(
                        "Redfish for the node %s is still in the %s status after all the retries. Giving up.",
                        node_id,
                        node_power_state,
                    )
                    return POWER_STATE.ERROR

                sleep_time = ((2**retries) - 1) / 2
                maaslog.error(
                    "Redfish for the node %s is in % status. Retring after %f seconds.",
                    node_id,
                    node_power_state,
                    sleep_time,
                )
                yield pause(sleep_time)
                return (
                    yield self._power_query(url, node_id, headers, retries + 1)
                )
            case _:
                maaslog.error(
                    "Redfish returned the unexpected power state '%s' for the BMC card in node %s.",
                    node_power_state,
                    node_id,
                )
                return POWER_STATE.ERROR

    @inlineCallbacks
    def _wait_for_status(self, desired_status, url, node_id, headers):
        for waiting_time in self.wait_time:
            current_status = yield self._power_query(url, node_id, headers)
            if current_status == desired_status:
                return
            maaslog.debug(
                f"Waiting for {node_id} to be {desired_status}. Current status is {current_status}."
            )
            yield pause(waiting_time)

        raise PowerActionError(
            f"The redfish node '{node_id.decode()}' did not transition to the state '{desired_status}'. The current status reported "
            f"by the BMC is '{current_status}'."
        )
