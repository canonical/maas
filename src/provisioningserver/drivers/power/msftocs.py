# Copyright 2015-2021 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""MicrosoftOCS Power Driver."""


from typing import Optional
import urllib.error
import urllib.parse
import urllib.request

from lxml.etree import fromstring

from provisioningserver.drivers import (
    make_ip_extractor,
    make_setting_field,
    SETTING_SCOPE,
)
from provisioningserver.drivers.power import (
    PowerActionError,
    PowerConnError,
    PowerDriver,
    PowerFatalError,
)
from provisioningserver.rpc.utils import commission_node, create_node
from provisioningserver.utils.twisted import synchronous


class MicrosoftOCSState:
    ON = "ON"
    OFF = "OFF"


class MicrosoftOCSPowerDriver(PowerDriver):
    name = "msftocs"
    chassis = True
    can_probe = True
    can_set_boot_order = False
    description = "Microsoft OCS - Chassis Manager"
    settings = [
        make_setting_field("power_address", "Power address", required=True),
        make_setting_field("power_port", "Power port"),
        make_setting_field("power_user", "Power user"),
        make_setting_field(
            "power_pass", "Power password", field_type="password", secret=True
        ),
        make_setting_field(
            "blade_id",
            "Blade ID (Typically 1-24)",
            scope=SETTING_SCOPE.NODE,
            required=True,
        ),
    ]
    ip_extractor = make_ip_extractor("power_address")

    def detect_missing_packages(self):
        # uses urllib2 http client - nothing to look for!
        return []

    def extract_from_response(self, response, element_tag):
        """Extract text from first element with element_tag in response."""
        root = fromstring(response)
        return root.findtext(
            ".//ns:%s" % element_tag, namespaces={"ns": root.nsmap[None]}
        )

    def get(self, command, context, params=None):
        """Dispatch a GET request to a Microsoft OCS chassis."""
        if params is None:
            params = []
        else:
            params = [param for param in params if bool(param)]
        url_base = "http://{power_address}:{power_port}/".format(**context)
        url = urllib.parse.urljoin(url_base, command) + "?" + "&".join(params)
        authinfo = urllib.request.HTTPPasswordMgrWithDefaultRealm()
        authinfo.add_password(
            None, url, context["power_user"], context["power_pass"]
        )
        proxy_handler = urllib.request.ProxyHandler({})
        auth_handler = urllib.request.HTTPBasicAuthHandler(authinfo)
        opener = urllib.request.build_opener(proxy_handler, auth_handler)
        urllib.request.install_opener(opener)
        try:
            response = urllib.request.urlopen(url)
        except urllib.error.HTTPError as e:
            raise PowerConnError(
                "Could not make proper connection to Microsoft OCS Chassis."
                " HTTP error code: %s" % e.code
            )
        except urllib.error.URLError as e:
            raise PowerConnError(
                "Could not make proper connection to Microsoft OCS Chassis."
                " Server could not be reached: %s" % e.reason
            )
        else:
            return response.read()

    def set_next_boot_device(
        self, context, pxe=False, uefi=False, persistent=False
    ):
        """Set Next Boot Device."""
        boot_pxe = "2" if pxe else "3"
        boot_uefi = "true" if uefi else "false"
        boot_persistent = "true" if persistent else "false"
        params = [
            "bladeid=%s" % context["blade_id"],
            "bootType=%s" % boot_pxe,
            "uefi=%s" % boot_uefi,
            "persistent=%s" % boot_persistent,
        ]
        self.get("SetNextBoot", context, params)

    def get_blades(self, context):
        """Gets available blades.

        Returns dictionary of blade numbers and their corresponding
        MAC Addresses.
        """
        blades = {}
        root = fromstring(self.get("GetChassisInfo", context))
        namespace = {"ns": root.nsmap[None]}
        blade_collections = root.find(
            ".//ns:bladeCollections", namespaces=namespace
        )
        # Iterate over all BladeInfo Elements
        for blade_info in blade_collections:
            blade_mac_address = blade_info.find(
                ".//ns:bladeMacAddress", namespaces=namespace
            )
            macs = []
            # Iterate over all NicInfo Elements and add MAC Addresses
            for nic_info in blade_mac_address:
                macs.append(
                    nic_info.findtext(".//ns:macAddress", namespaces=namespace)
                )
            macs = [mac for mac in macs if bool(mac)]
            if macs:
                # Retrive blade id number
                bladeid = blade_info.findtext(
                    ".//ns:bladeNumber", namespaces=namespace
                )
                # Add MAC Addresses for blade
                blades[bladeid] = macs

        return blades

    def power_on(self, system_id, context):
        """Power on MicrosoftOCS blade."""
        if self.power_query(system_id, context) == "on":
            self.power_off(system_id, context)
        try:
            # Set default (persistent) boot to HDD
            self.set_next_boot_device(context, persistent=True)
            # Set next boot to PXE
            self.set_next_boot_device(context, pxe=True)
            # Power on blade
            self.get(
                "SetBladeOn", context, ["bladeid=%s" % context["blade_id"]]
            )
        except PowerConnError as e:
            raise PowerActionError(
                "MicrosoftOCS Power Driver unable to power on blade_id %s: %s"
                % (context["blade_id"], e)
            )

    def power_off(self, system_id, context):
        """Power off MicrosoftOCS blade."""
        try:
            # Power off blade
            self.get(
                "SetBladeOff", context, ["bladeid=%s" % context["blade_id"]]
            )
        except PowerConnError as e:
            raise PowerActionError(
                "MicrosoftOCS Power Driver unable to power off blade_id %s: %s"
                % (context["blade_id"], e)
            )

    def power_query(self, system_id, context):
        """Power query MicrosoftOCS blade."""
        try:
            power_state = self.extract_from_response(
                self.get(
                    "GetBladeState",
                    context,
                    ["bladeid=%s" % context["blade_id"]],
                ),
                "bladeState",
            )
        except PowerConnError as e:
            raise PowerActionError(
                "MicrosoftOCS Power Driver unable to power query blade_id %s:"
                " %r" % (context["blade_id"], e)
            )
        else:
            if power_state == MicrosoftOCSState.OFF:
                return "off"
            elif power_state == MicrosoftOCSState.ON:
                return "on"
            else:
                raise PowerFatalError(
                    "MicrosoftOCS Power Driver retrieved unknown power state"
                    " %s for blade_id %s" % (power_state, context["blade_id"])
                )


@synchronous
def probe_and_enlist_msftocs(
    user: str,
    ip: str,
    port: Optional[int],
    username: Optional[str],
    password: Optional[str],
    accept_all: bool = False,
    domain: str = None,
):
    """Extracts all of nodes from msftocs, sets all of them to boot via
    HDD by, default, sets them to bootonce via PXE, and then enlists them
    into MAAS.
    """
    # The default port for a MicrosoftOCS chassis is 8000. We expect an
    # integer from the AddChassis RPC call.
    port = 8000 if port is None or port == 0 else port

    msftocs_driver = MicrosoftOCSPowerDriver()
    context = {
        "power_address": ip,
        "power_port": str(port),
        "power_user": username,
        "power_pass": password,
    }
    try:
        # if get_blades works, we have access to the system
        blades = msftocs_driver.get_blades(context)
    except urllib.error.HTTPError as e:
        raise PowerFatalError(
            "Failed to probe nodes for Microsoft OCS with ip=%s "
            "port=%s, username=%s, password=%s. HTTP error code: %s"
            % (ip, port, username, password, e.code)
        )
    except urllib.error.URLError as e:
        raise PowerFatalError(
            "Failed to probe nodes for Microsoft OCS with ip=%s "
            "port=%s, username=%s, password=%s. "
            "Server could not be reached: %s"
            % (ip, port, username, password, e.reason)
        )
    else:
        for blade_id, macs in blades.items():
            context["blade_id"] = blade_id
            # Set default (persistent) boot to HDD
            msftocs_driver.set_next_boot_device(context, persistent=True)
            # Set next boot to PXE
            msftocs_driver.set_next_boot_device(context, pxe=True)
            system_id = create_node(
                macs, "amd64", "msftocs", context, domain
            ).wait(30)

            if accept_all:
                commission_node(system_id, user).wait(30)
