# Copyright 2014-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Support for managing nodes via Cisco UCS Manager's HTTP-XML API.

It's useful to have a cursory understanding of how UCS Manager XML API
works. Cisco has a proprietary document that describes all of this in
more detail, and I would suggest you get a copy of that if you want more
information than is provided here.

The Cisco DevNet website for UCS Manager has a link to the document,
which is behind a login wall, and links to example UCS queries:

https://developer.cisco.com/web/unifiedcomputing/home

UCS Manager is a tool for managing servers. It provides an XML API for
external applications to use to interact with UCS Manager to manage
servers. The API is available via HTTP, and requests and responses are
made of XML strings. MAAS's code for interacting with a UCS Manager is
concerned with building these requests, sending them to UCS Manager, and
processing the responses.

UCS Manager stores information in a hierarchical structure known as the
management information tree. This structure is exposed via the XML API,
where we can manipulate objects in the tree by finding them, reading
them, and writing them.

Some definitions for terms that are used in this code:

Boot Policy - Controls the boot order for a server. Each service profile
is associated with a boot policy.

Distinguished Name (DN) - Each object in UCS has a unique DN, which
describes its position in the tree. This is like a fully qualified path,
and provides a way for objects to reference other objects at other
places in the tree, or for API users to look up specific objects in the
tree.

Class - Classes define the properties and states of objects. An object's
class is given in its tag name.

Managed Object (MO) - An object in the management information tree.
Objects are recursive, and may have children of multiple types. With the
exception of the root object, all objects have parents. In the XML API,
objects are represented as XML elements.

Method - Actions performed by the API on managed objects. These can
change state, or read the current state, or both.

Server - A physical server managed by UCS Manager. Servers must be
associated with service profiles in order to be used.

Service Profile - A set of configuration options for a server. Service
profiles define the server's personality, and can be migrated from
server to server. Service profiles describe boot policy, MAC addresses,
network connectivity, IPMI configuration, and more. MAAS requires
servers to be associated with service profiles.

UUID - The UUID for a server. MAAS persists the UUID of each UCS managed
server it enlists, and uses it as a key for looking the server up later.
"""

import contextlib
from typing import Optional
import urllib.error
import urllib.parse
import urllib.request

from lxml.etree import Element, tostring, XML

from provisioningserver.rpc.utils import commission_node, create_node
from provisioningserver.utils.twisted import synchronous


class UCSM_XML_API_Error(Exception):
    """Failure talking to a Cisco UCS Manager."""

    def __init__(self, msg, code=None):
        super().__init__(msg)
        self.code = code


def make_request_data(name, fields=None, children=None):
    """Build a request string for an API method."""
    root = Element(name, fields)
    if children is not None:
        root.extend(children)
    return tostring(root)


def parse_response(response_string):
    """Parse the response from an API method."""
    doc = XML(response_string)

    error_code = doc.get("errorCode")
    if error_code is not None:
        raise UCSM_XML_API_Error(doc.get("errorDescr"), error_code)

    return doc


class UCSM_XML_API:
    """Provides access to a Cisco UCS Manager's XML API. Public methods
    on this class correspond to UCS Manager XML API methods.

    Each request uses a new connection. The server supports keep-alive,
    so this client could be optimized to use it too.
    """

    def __init__(self, url, username, password):
        self.url = url
        self.api_url = urllib.parse.urljoin(self.url, "nuova")
        self.username = username
        self.password = password
        self.cookie = None

    def _send_request(self, request_data):
        """Issue a request via HTTP and parse the response."""
        request = urllib.request.Request(self.api_url, request_data)
        response = urllib.request.urlopen(request)
        response_text = response.read()
        response_doc = parse_response(response_text)
        return response_doc

    def _call(self, name, fields=None, children=None):
        request_data = make_request_data(name, fields, children)
        response = self._send_request(request_data)
        return response

    def login(self):
        """Login to the API and get a cookie.

        Logging into the API gives a new cookie in response. The cookie
        will become inactive after it has been inactive for some amount
        of time (10 minutes is the default.)

        UCS Manager allows a limited number of active cookies at any
        point in time, so it's important to free the cookie up when
        finished by logging out via the ``logout`` method.
        """
        fields = {"inName": self.username, "inPassword": self.password}
        response = self._call("aaaLogin", fields)
        self.cookie = response.get("outCookie")

    def logout(self):
        """Logout from the API and free the cookie."""
        fields = {"inCookie": self.cookie}
        self._call("aaaLogout", fields)
        self.cookie = None

    def config_resolve_class(self, class_id, filters=None):
        """Issue a configResolveClass request.

        This returns all of the objects of class ``class_id`` from the
        UCS Manager.

        Filters provide a way of limiting the classes returned according
        to their attributes. There are a number of filters available -
        Cisco's XML API documentation has a full chapter on filters.
        All we care about here is that filters are described with XML
        elements.
        """
        fields = {"cookie": self.cookie, "classId": class_id}

        in_filters = Element("inFilter")
        if filters:
            in_filters.extend(filters)

        return self._call("configResolveClass", fields, [in_filters])

    def config_resolve_children(self, dn, class_id=None):
        """Issue a configResolveChildren request.

        This returns all of the children of the object named by ``dn``,
        or if ``class_id`` is not None, all of the children of type
        ``class_id``.
        """
        fields = {"cookie": self.cookie, "inDn": dn}
        if class_id is not None:
            fields["classId"] = class_id
        return self._call("configResolveChildren", fields)

    def config_resolve_dn(self, dn):
        """Retrieve a single object by name.

        This returns the object named by ``dn``, but not its children.
        """
        fields = {"cookie": self.cookie, "dn": dn}
        return self._call("configResolveDn", fields)

    def config_conf_mo(self, dn, config_items):
        """Issue a configConfMo request.

        This makes a configuration change on an object (MO).
        """
        fields = {"cookie": self.cookie, "dn": dn}

        in_configs = Element("inConfig")
        in_configs.extend(config_items)

        self._call("configConfMo", fields, [in_configs])


def get_servers(api, uuid=None):
    """Retrieve a list of servers from the UCS Manager."""
    if uuid:
        attrs = {"class": "computeItem", "property": "uuid", "value": uuid}
        filters = [Element("eq", attrs)]
    else:
        filters = None

    resolved = api.config_resolve_class("computeItem", filters)
    return resolved.xpath("//outConfigs/*")


def get_children(api, element, class_id):
    """Retrieve a list of child elements from the UCS Manager."""
    resolved = api.config_resolve_children(element.get("dn"), class_id)
    return resolved.xpath("//outConfigs/%s" % class_id)


def get_macs(api, server):
    """Retrieve the list of MAC addresses assigned to a server.

    Network interfaces are represented by 'adaptorUnit' objects, and
    are stored as children of servers.
    """
    adaptors = get_children(api, server, "adaptorUnit")

    macs = []
    for adaptor in adaptors:
        host_eth_ifs = get_children(api, adaptor, "adaptorHostEthIf")
        macs.extend([h.get("mac") for h in host_eth_ifs])

    return macs


def probe_lan_boot_options(api, server):
    """Probe for LAN boot options available on a server."""
    service_profile = get_service_profile(api, server)
    boot_profile_dn = service_profile.get("operBootPolicyName")
    response = api.config_resolve_children(boot_profile_dn)
    return response.xpath("//outConfigs/lsbootLan")


def probe_servers(api):
    """Retrieve the UUID and MAC addresses for servers from the UCS Manager."""
    servers = get_servers(api)

    server_list = []
    for s in servers:
        # If the server does not have any MAC, then we don't add it.
        if not get_macs(api, s):
            continue
        # If the server does not have LAN boot option (can't boot from LAN),
        # then we don't add it.
        if not probe_lan_boot_options(api, s):
            continue
        server_list.append((s, get_macs(api, s)))

    return server_list


def get_server_power_control(api, server):
    """Retrieve the power control object for a server."""
    service_profile_dn = server.get("assignedToDn")
    resolved = api.config_resolve_children(service_profile_dn, "lsPower")
    power_controls = resolved.xpath("//outConfigs/lsPower")
    return power_controls[0]


def set_server_power_control(api, power_control, command):
    """Issue a power command to a server's power control."""
    attrs = {"state": command, "dn": power_control.get("dn")}
    power_change = Element("lsPower", attrs)
    api.config_conf_mo(power_control.get("dn"), [power_change])


def get_service_profile(api, server):
    """Get the server's assigned service profile."""
    service_profile_dn = server.get("assignedToDn")
    result = api.config_resolve_dn(service_profile_dn)
    service_profile = result.xpath("//outConfig/lsServer")[0]
    return service_profile


def get_first_booter(boot_profile_response):
    """Find the device currently set to boot by default."""
    # The 'order' attribue is a positive integer. The device with the
    # lowest order gets booted first.
    orders = boot_profile_response.xpath("//outConfigs/*/@order")
    ordinals = map(int, orders)
    top_boot_order = min(ordinals)
    first_query = "//outConfigs/*[@order=%s]" % top_boot_order
    current_first = boot_profile_response.xpath(first_query)[0]
    return current_first


RO_KEYS = ["access", "type"]


def strip_ro_keys(elements):
    """Remove read-only keys from configuration elements.

    These are keys for attributes that aren't allowed to be changed via
    configConfMo request. They are included in MO's that we read from the
    API; stripping these attributes lets us reuse the elements for those
    MO's rather than building new ones from scratch.
    """
    for ro_key in RO_KEYS:
        for element in elements:
            del element.attrib[ro_key]


def make_policy_change(boot_profile_response):
    """Build the policy change tree required to make LAN boot first
    priority.

    The original top priority will be swapped with LAN boot's original
    priority.
    """
    current_first = get_first_booter(boot_profile_response)
    lan_boot = boot_profile_response.xpath("//outConfigs/lsbootLan")[0]

    if current_first == lan_boot:
        return

    top_boot_order = current_first.get("order")
    current_first.set("order", lan_boot.get("order"))
    lan_boot.set("order", top_boot_order)

    elements = [current_first, lan_boot]
    strip_ro_keys(elements)
    policy_change = Element("lsbootPolicy")
    policy_change.extend(elements)
    return policy_change


def set_lan_boot_default(api, server):
    """Set a server to boot via LAN by default.

    If LAN boot is already the top priority, no change will
    be made.

    This command changes the server's boot profile, which will affect
    any other servers also using that boot profile. This is ok, because
    probe and enlist enlists all the servers in the chassis.
    """
    service_profile = get_service_profile(api, server)
    boot_profile_dn = service_profile.get("operBootPolicyName")
    response = api.config_resolve_children(boot_profile_dn)
    policy_change = make_policy_change(response)
    if policy_change is None:
        return
    api.config_conf_mo(boot_profile_dn, [policy_change])


@contextlib.contextmanager
def logged_in(url, username, password):
    """Context manager that ensures the logout from the API occurs."""
    api = UCSM_XML_API(url, username, password)
    api.login()
    try:
        yield api
    finally:
        api.logout()


def get_power_command(maas_power_mode, current_state):
    """Translate a MAAS on/off state into a UCSM power command.

    If the node is up already and receives a request to power on, power
    cycle the node.
    """
    if maas_power_mode == "on":
        if current_state == "up":
            return "cycle-immediate"
        return "admin-up"
    elif maas_power_mode == "off":
        return "admin-down"
    else:
        raise UCSM_XML_API_Error(
            "Unexpected maas power mode: %s" % maas_power_mode, None
        )


def power_control_ucsm(url, username, password, uuid, maas_power_mode):
    """Handle calls from the power template for nodes with a power type
    of 'ucsm'.
    """
    with logged_in(url, username, password) as api:
        # UUIDs are unique per server, so we get either one or zero
        # servers for a given UUID.
        [server] = get_servers(api, uuid)
        power_control = get_server_power_control(api, server)
        command = get_power_command(maas_power_mode, server.get("operPower"))
        set_server_power_control(api, power_control, command)


def power_state_ucsm(url, username, password, uuid):
    """Return the power state for the ucsm machine."""
    with logged_in(url, username, password) as api:
        # UUIDs are unique per server, so we get either one or zero
        # servers for a given UUID.
        [server] = get_servers(api, uuid)
        power_state = server.get("operPower")

        if power_state in ("on", "off"):
            return power_state
        raise UCSM_XML_API_Error("Unknown power state: %s" % power_state, None)


@synchronous
def probe_and_enlist_ucsm(
    user: str,
    url: str,
    username: Optional[str],
    password: Optional[str],
    accept_all: bool = False,
    domain: str = None,
):
    """Probe a UCS Manager and enlist all its servers.

    Here's what happens here: 1. Get a list of servers from the UCS
    Manager, along with their MAC addresses.

    2. Configure each server to boot from LAN first.

    3. Add each server to MAAS as a new node, with a power control
    method of 'ucsm'. The URL and credentials supplied are persisted
    with each node so MAAS knows how to access UCSM to manage the node
    in the future.

    This code expects each server in the system to have already been
    associated with a service profile. The servers must have networking
    configured, and their boot profiles must include a boot from LAN
    option. During enlistment, the boot profile for each service profile
    used by a server will be modified to move LAN boot to the highest
    priority boot option.

    Also, if any node fails to enlist, this enlistment process will
    stop and won't attempt to enlist any additional nodes. If a node is
    already known to MAAS, it will fail to enlist, so all nodes must be
    added at once.

    There is also room for optimization during enlistment. While our
    client deals with a single server at a time, the API is capable
    of reading/writing the settings of multiple servers in the same
    request.
    """
    with logged_in(url, username, password) as api:
        servers = probe_servers(api)
        for server, _ in servers:
            set_lan_boot_default(api, server)

    for server, macs in servers:
        params = {
            "power_address": url,
            "power_user": username,
            "power_pass": password,
            "uuid": server.get("uuid"),
        }
        system_id = create_node(macs, "amd64", "ucsm", params, domain).wait(30)

        if accept_all:
            commission_node(system_id, user).wait(30)
