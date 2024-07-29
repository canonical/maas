# Copyright 2019-2021 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""OpenBMC Power Driver."""


from http import HTTPStatus
from http.cookiejar import CookieJar
from io import BytesIO
import json
from os.path import join

from twisted.internet import reactor
from twisted.internet.defer import inlineCallbacks
from twisted.web.client import Agent, CookieAgent, FileBodyProducer, readBody
from twisted.web.http_headers import Headers

from provisioningserver.drivers import make_ip_extractor, make_setting_field
from provisioningserver.drivers.power import (
    PowerActionError,
    PowerDriver,
    PowerFatalError,
)
from provisioningserver.drivers.power.utils import WebClientContextFactory
from provisioningserver.utils.twisted import asynchronous

# OpenBMC RESTful uri path
HOST_CONTROL = "/xyz/openbmc_project/control/host0/boot/"
HOST_STATE = "/xyz/openbmc_project/state/host0/attr/"

# OpenBMC RESTful control data
HOST_OFF = {"data": "xyz.openbmc_project.State.Host.Transition.Off"}
HOST_ON = {"data": "xyz.openbmc_project.State.Host.Transition.On"}
SRC_NET = {"data": "xyz.openbmc_project.Control.Boot.Source.Sources.Network"}
REG_MODE = {"data": "xyz.openbmc_project.Control.Boot.Mode.Modes.Regular"}


class OpenBMCPowerDriver(PowerDriver):
    chassis = False
    can_probe = False
    can_set_boot_order = False

    name = "openbmc"
    description = "OpenBMC Power Driver"
    settings = [
        make_setting_field(
            "power_address",
            "OpenBMC address",
            field_type="ip_address",
            required=True,
        ),
        make_setting_field("power_user", "OpenBMC user", required=True),
        make_setting_field(
            "power_pass",
            "OpenBMC password",
            field_type="password",
            required=True,
            secret=True,
        ),
    ]
    ip_extractor = make_ip_extractor("power_address")

    cookie_jar = CookieJar()
    agent = CookieAgent(
        Agent(reactor, contextFactory=WebClientContextFactory()), cookie_jar
    )

    def detect_missing_packages(self):
        # no required packages
        return []

    @asynchronous
    def openbmc_request(self, method, uri, data=None):
        """Send the RESTful request and return the response."""
        d = self.agent.request(
            method,
            uri,
            Headers({b"Content-Type": [b"application/json"]}),
            data,
        )

        def cb_request(response):
            """Render the response received."""

            def decode_data(data):
                data = data.decode("utf-8")
                return json.loads(data)

            # Error out if the response has a status code of 400 or above.
            if response.code >= int(HTTPStatus.BAD_REQUEST):
                raise PowerActionError(
                    "OpenBMC request failed with response status code:"
                    " %s." % response.code
                )

            f = readBody(response)
            f.addCallback(decode_data)
            return f

        d.addCallback(cb_request)
        return d

    def get_uri(self, context, path=None):
        """Return url for the host."""
        uri = context.get("power_address")
        if path is not None:
            uri = uri + path
        if "https" not in uri and "http" not in uri:
            uri = join("https://", uri)
        return uri.encode("utf-8")

    @inlineCallbacks
    def command(self, context, method, uri, data=None):
        """Current deployments of OpenBMC in the field do not
        support header based authentication. To issue RESTful commands,
        we need to login, issue RESTful command and logout.
        """
        # login to BMC
        login_uri = self.get_uri(context, "/login")
        login_creds = {
            "data": [context.get("power_user"), context.get("power_pass")]
        }
        login_data = FileBodyProducer(
            BytesIO(json.dumps(login_creds).encode("utf-8"))
        )
        login = yield self.openbmc_request(b"POST", login_uri, login_data)
        login_status = login.get("status")
        if login_status.lower() != "ok":
            raise PowerFatalError(
                "OpenBMC power driver received unexpected response"
                " to login command"
            )
        # issue command
        cmd_out = yield self.openbmc_request(method, uri, data)
        # logout of BMC
        logout_uri = self.get_uri(context, "/logout")
        logout_creds = {"data": []}
        logout_data = FileBodyProducer(
            BytesIO(json.dumps(logout_creds).encode("utf-8"))
        )
        logout = yield self.openbmc_request(b"POST", logout_uri, logout_data)
        logout_status = logout.get("status")
        if logout_status.lower() != "ok":
            raise PowerFatalError(
                "OpenBMC power driver received unexpected response"
                " to logout command"
            )
        return cmd_out

    @inlineCallbacks
    def set_pxe_boot(self, context):
        """Set the host to PXE boot."""
        # set boot mode to one-time boot.
        uri = self.get_uri(context, HOST_CONTROL + "one_time/attr/BootMode")
        data = FileBodyProducer(BytesIO(json.dumps(REG_MODE).encode("utf-8")))
        yield self.command(context, b"PUT", uri, data)
        # set one-time boot source to network.
        uri = self.get_uri(context, HOST_CONTROL + "one_time/attr/BootSource")
        data = FileBodyProducer(BytesIO(json.dumps(SRC_NET).encode("utf-8")))
        yield self.command(context, b"PUT", uri, data)

    @asynchronous
    @inlineCallbacks
    def power_query(self, system_id, context):
        """Power query host."""
        uri = self.get_uri(context, HOST_STATE + "CurrentHostState")
        power_state = yield self.command(context, b"GET", uri, None)
        status = power_state.get("data").split(".")[-1].lower()
        if all(status not in state for state in ("running", "off")):
            raise PowerFatalError(
                "OpenBMC power driver received unexpected response"
                "to power query command"
            )
        return {"running": "on", "off": "off"}.get(status)

    @asynchronous
    @inlineCallbacks
    def power_on(self, system_id, context):
        """Power on host."""
        cur_state = yield self.power_query(system_id, context)
        uri = self.get_uri(context, HOST_STATE + "RequestedHostTransition")
        # power off host if it is currently on.
        if cur_state == "on":
            data = FileBodyProducer(
                BytesIO(json.dumps(HOST_OFF).encode("utf-8"))
            )
            off_state = yield self.command(context, b"PUT", uri, data)
            status = off_state.get("status")
            if status.lower() != "ok":
                raise PowerFatalError(
                    "OpenBMC power driver received unexpected response"
                    " to power off command"
                )
        # set one-time boot to PXE boot.
        yield self.set_pxe_boot(context)
        # power on host.
        data = FileBodyProducer(BytesIO(json.dumps(HOST_ON).encode("utf-8")))
        on_state = yield self.command(context, b"PUT", uri, data)
        status = on_state.get("status")
        if status.lower() != "ok":
            raise PowerFatalError(
                "OpenBMC power driver received unexpected response"
                " to power on command"
            )

    @asynchronous
    @inlineCallbacks
    def power_off(self, system_id, context):
        """Power off host."""
        uri = self.get_uri(context, HOST_STATE + "RequestedHostTransition")
        data = FileBodyProducer(BytesIO(json.dumps(HOST_OFF).encode("utf-8")))
        # set next one-time boot to PXE boot.
        yield self.set_pxe_boot(context)
        # power off host.
        power_state = yield self.command(context, b"PUT", uri, data)
        status = power_state.get("status")
        if status.lower() != "ok":
            raise PowerFatalError(
                "OpenBMC power driver received unexpected response"
                " to power off command"
            )
