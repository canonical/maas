# Copyright 2017-2025 christmann informationstechnik + medien GmbH & Co. KG. This
# software is licensed under the GNU Affero General Public License version 3
# (see the file LICENSE).

"""Christmann RECS|Box Power Driver."""

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
from provisioningserver.drivers.power import PowerConnError, PowerDriver
from provisioningserver.logger import get_maas_logger
from provisioningserver.rpc.utils import commission_node, create_node
from provisioningserver.utils.twisted import synchronous

maaslog = get_maas_logger("drivers.power.recs")


def extract_recs_parameters(context):
    ip = context.get("power_address")
    port = context.get("power_port")
    username = context.get("power_user")
    password = context.get("power_pass")
    node_id = context.get("node_id")
    return ip, port, username, password, node_id


class RECSError(Exception):
    """Failure talking to a RECS_Master."""


class RECSAPI:
    """API to communicate with a RECS_Master"""

    def __init__(self, ip, port, username, password):
        """
        :param ip: The IP address of the RECS_Master
          e.g.: "192.168.0.1"
        :type ip: string
        :param port: The http port to connect to the RECS_Master,
          e.g.: "80"
        :type port: string
        :param username: The username for authentication to RECS_Master,
          e.g.: "admin"
        :type username: string
        :param password: The password for authentication to the RECS_Master,
          e.g.: "admin"
        :type password: string
        """
        self.ip = ip
        self.port = port
        self.username = username
        self.password = password

    def build_url(self, command, params=None):
        if params is None:
            params = []
        url = f"http://{self.ip}:{self.port}/REST/"
        params = filter(None, params)
        return urllib.parse.urljoin(url, command) + "?" + "&".join(params)

    def extract_from_response(self, response, attribute):
        """Extract attribute from first element in response."""
        root = fromstring(response)
        return root.attrib.get(attribute)

    def get(self, command, params=None):
        """Dispatch a GET request to a RECS_Master."""
        if params is None:
            params = []
        url = self.build_url(command, params)
        authinfo = urllib.request.HTTPPasswordMgrWithDefaultRealm()
        authinfo.add_password(None, url, self.username, self.password)
        proxy_handler = urllib.request.ProxyHandler({})
        auth_handler = urllib.request.HTTPBasicAuthHandler(authinfo)
        opener = urllib.request.build_opener(proxy_handler, auth_handler)
        urllib.request.install_opener(opener)
        try:
            response = urllib.request.urlopen(url)
        except urllib.error.HTTPError as e:
            raise PowerConnError(  # noqa: B904
                "Could not make proper connection to RECS|Box."
                " HTTP error code: %s" % e.code
            )
        except urllib.error.URLError as e:
            raise PowerConnError(  # noqa: B904
                "Could not make proper connection to RECS|Box."
                " Server could not be reached: %s" % e.reason
            )
        else:
            return response.read()

    def post(self, command, urlparams=None, params=None):
        """Dispatch a POST request to a RECS_Master."""
        if params is None:
            params = {}
        if urlparams is None:
            urlparams = []
        url = self.build_url(command, urlparams)
        authinfo = urllib.request.HTTPPasswordMgrWithDefaultRealm()
        authinfo.add_password(None, url, self.username, self.password)
        proxy_handler = urllib.request.ProxyHandler({})
        auth_handler = urllib.request.HTTPBasicAuthHandler(authinfo)
        opener = urllib.request.build_opener(proxy_handler, auth_handler)
        urllib.request.install_opener(opener)
        data = urllib.parse.urlencode(params).encode()
        req = urllib.request.Request(url, data, method="POST")
        try:
            response = urllib.request.urlopen(req)
        except urllib.error.HTTPError as e:
            raise PowerConnError(  # noqa: B904
                "Could not make proper connection to RECS|Box."
                " HTTP error code: %s" % e.code
            )
        except urllib.error.URLError as e:
            raise PowerConnError(  # noqa: B904
                "Could not make proper connection to RECS|Box."
                " Server could not be reached: %s" % e.reason
            )
        else:
            return response.read()

    def put(self, command, urlparams=None, params=None):
        """Dispatch a PUT request to a RECS_Master."""
        if params is None:
            params = {}
        if urlparams is None:
            urlparams = []
        url = self.build_url(command, urlparams)
        authinfo = urllib.request.HTTPPasswordMgrWithDefaultRealm()
        authinfo.add_password(None, url, self.username, self.password)
        proxy_handler = urllib.request.ProxyHandler({})
        auth_handler = urllib.request.HTTPBasicAuthHandler(authinfo)
        opener = urllib.request.build_opener(proxy_handler, auth_handler)
        urllib.request.install_opener(opener)
        data = urllib.parse.urlencode(params).encode()
        req = urllib.request.Request(url, data, method="PUT")
        try:
            response = urllib.request.urlopen(req)
        except urllib.error.HTTPError as e:
            raise PowerConnError(  # noqa: B904
                "Could not make proper connection to RECS|Box."
                " HTTP error code: %s" % e.code
            )
        except urllib.error.URLError as e:
            raise PowerConnError(  # noqa: B904
                "Could not make proper connection to RECS|Box."
                " Server could not be reached: %s" % e.reason
            )
        else:
            return response.read()

    def get_node_power_state(self, nodeid):
        """Gets the power state of the node."""
        return self.extract_from_response(
            self.get("node/%s" % nodeid), "state"
        )

    def _set_power(self, nodeid, action):
        """Set power for node."""
        self.post(f"node/{nodeid}/manage/{action}")

    def set_power_off_node(self, nodeid):
        """Turns power to node off."""
        return self._set_power(nodeid, "power_off")

    def set_power_on_node(self, nodeid):
        """Turns power to node on."""
        return self._set_power(nodeid, "power_on")

    def set_boot_source(self, nodeid, source, persistent):
        """Set boot source of node."""
        self.put(
            "node/%s/manage/set_bootsource" % nodeid,
            params={"source": source, "persistent": persistent},
        )

    def get_nodes(self):
        """Gets available nodes.

        Returns dictionary of node IDs, their corresponding
        MAC Addresses and architecture.
        """
        nodes = {}
        xmldata = self.get("node")
        root = fromstring(xmldata)

        # Iterate over all node Elements
        for node_info in root:
            macs = []
            # Add both MACs if available
            macs.append(node_info.attrib.get("macAddressMgmt"))
            macs.append(node_info.attrib.get("macAddressCompute"))
            macs = list(filter(None, macs))
            if macs:
                # Retrive node id
                nodeid = node_info.attrib.get("id")
                # Retrive architecture
                arch = node_info.attrib.get("architecture")
                # Add data for node
                nodes[nodeid] = {"macs": macs, "arch": arch}

        return nodes


class RECSPowerDriver(PowerDriver):
    name = "recs_box"
    chassis = True
    can_probe = True
    can_set_boot_order = False
    description = "Christmann RECS|Box Power Driver"
    settings = [
        make_setting_field(
            "node_id", "Node ID", scope=SETTING_SCOPE.NODE, required=True
        ),
        make_setting_field(
            "power_address",
            "Power address",
            field_type="ip_address",
            required=True,
        ),
        make_setting_field("power_port", "Power port"),
        make_setting_field("power_user", "Power user"),
        make_setting_field(
            "power_pass", "Power password", field_type="password", secret=True
        ),
    ]
    ip_extractor = make_ip_extractor("power_address")

    def power_control_recs(
        self, ip, port, username, password, node_id, power_change
    ):
        """Control the power state for the given node."""

        port = 8000 if port is None or port == 0 else port
        api = RECSAPI(ip, port, username, password)

        if power_change == "on":
            api.set_power_on_node(node_id)
        elif power_change == "off":
            api.set_power_off_node(node_id)
        else:
            raise RECSError("Unexpected MAAS power mode: %s" % power_change)

    def power_state_recs(self, ip, port, username, password, node_id):
        """Return the power state for the given node."""

        port = 8000 if port is None or port == 0 else port
        api = RECSAPI(ip, port, username, password)

        try:
            power_state = api.get_node_power_state(node_id)
        except urllib.error.HTTPError as e:
            raise RECSError(  # noqa: B904
                "Failed to retrieve power state. HTTP error code: %s" % e.code
            )
        except urllib.error.URLError as e:
            raise RECSError(  # noqa: B904
                "Failed to retrieve power state. Server not reachable: %s"
                % e.reason
            )

        if power_state == "1":
            return "on"
        return "off"

    def set_boot_source_recs(
        self, ip, port, username, password, node_id, source, persistent
    ):
        """Control the boot source for the given node."""

        port = 8000 if port is None or port == 0 else port
        api = RECSAPI(ip, port, username, password)

        api.set_boot_source(node_id, source, persistent)

    def detect_missing_packages(self):
        # uses urllib http client - nothing to look for!
        return []

    def power_on(self, system_id, context):
        """Power on RECS node."""
        power_change = "on"
        ip, port, username, password, node_id = extract_recs_parameters(
            context
        )

        # Set default (persistent) boot to HDD
        self.set_boot_source_recs(
            ip, port, username, password, node_id, "HDD", True
        )
        # Set next boot to PXE
        self.set_boot_source_recs(
            ip, port, username, password, node_id, "PXE", False
        )
        self.power_control_recs(
            ip, port, username, password, node_id, power_change
        )

    def power_off(self, system_id, context):
        """Power off RECS node."""
        power_change = "off"
        ip, port, username, password, node_id = extract_recs_parameters(
            context
        )
        self.power_control_recs(
            ip, port, username, password, node_id, power_change
        )

    def power_query(self, system_id, context):
        """Power query RECS node."""
        ip, port, username, password, node_id = extract_recs_parameters(
            context
        )
        return self.power_state_recs(ip, port, username, password, node_id)

    def power_reset(self, system_id, context):
        """Power reset RECS node."""
        raise NotImplementedError()


@synchronous
def probe_and_enlist_recs(
    user: str,
    ip: str,
    port: Optional[int],
    username: Optional[str],
    password: Optional[str],
    accept_all: bool = False,
    domain: str = None,
):
    maaslog.info("Probing for RECS servers as %s@%s", username, ip)

    port = 80 if port is None or port == 0 else port
    api = RECSAPI(ip, port, username, password)

    try:
        # if get_nodes works, we have access to the system
        nodes = api.get_nodes()
    except urllib.error.HTTPError as e:
        raise RECSError(  # noqa: B904
            "Failed to probe nodes for RECS_Master with ip=%s "
            "port=%s, username=%s, password=%s. HTTP error code: %s"
            % (ip, port, username, password, e.code)
        )
    except urllib.error.URLError as e:
        raise RECSError(  # noqa: B904
            "Failed to probe nodes for RECS_Master with ip=%s "
            "port=%s, username=%s, password=%s. "
            "Server could not be reached: %s"
            % (ip, port, username, password, e.reason)
        )

    for node_id, data in nodes.items():
        params = {
            "power_address": ip,
            "power_port": port,
            "power_user": username,
            "power_pass": password,
            "node_id": node_id,
        }
        arch = "amd64"
        if data["arch"] == "arm":
            arch = "armhf"

        maaslog.info(
            "Creating RECS node %s with MACs: %s", node_id, data["macs"]
        )

        # Set default (persistent) boot to HDD
        api.set_boot_source(node_id, "HDD", True)
        # Set next boot to PXE
        api.set_boot_source(node_id, "PXE", False)

        system_id = create_node(
            data["macs"], arch, "recs_box", params, domain
        ).wait(30)

        if accept_all:
            commission_node(system_id, user).wait(30)
