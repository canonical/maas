from django.db.models.expressions import RawSQL
from netaddr import IPAddress, IPNetwork

from maasserver.enum import INTERFACE_TYPE, IPADDRESS_TYPE, NODE_STATUS
from maasserver.models.config import Config
from maasserver.models.fabric import Fabric
from maasserver.models.interface import (
    BondInterface,
    BridgeInterface,
    Interface,
    PhysicalInterface,
    VLANInterface,
)
from maasserver.models.staticipaddress import StaticIPAddress
from maasserver.models.subnet import Subnet
from maasserver.models.vlan import VLAN
from maasserver.utils.orm import transactional
from provisioningserver.events import EVENT_TYPES
from provisioningserver.logger import get_maas_logger
from provisioningserver.utils import flatten, sorttop
from provisioningserver.utils.ipaddr import is_ipoib_mac
from provisioningserver.utils.network import fix_link_addresses
from provisioningserver.utils.twisted import synchronous

maaslog = get_maas_logger("metadataserver.network")
SWITCH_OPENBMC_MAC = "02:00:00:00:00:02"


def get_interface_dependencies(data):
    dependencies = {name: [] for name in data["networks"]}
    for name, network in data["networks"].items():
        if network["bridge"]:
            parents = network["bridge"]["upper_devices"]
        elif network["bond"]:
            parents = network["bond"]["lower_devices"]
        elif network["vlan"]:
            parents = [network["vlan"]["lower_device"]]
        else:
            parents = []
        # Only add devices that are defined in the data. Some virtual
        # interfaces might be defined as a parent, but they are not a
        # network, so we don't have any information about them.
        dependencies[name].extend(
            iface for iface in parents if iface in data["networks"]
        )
    return dependencies


def get_address_extra(config):
    extra = {}
    for info in config.values():
        for link in info["links"]:
            extra[str(IPNetwork(link["address"]).ip)] = {
                "mode": link.get("mode", "static"),
                "gateway": link.get("gateway"),
            }
    return extra


def _hardware_sync_network_device_notify(node, net_device, action):
    from metadataserver.builtin_scripts.hooks import _hardware_sync_notify

    _hardware_sync_notify(
        EVENT_TYPES.NODE_HARDWARE_SYNC_INTERFACE,
        node,
        net_device.name,
        action,
        device_type="interface",
    )


@synchronous
@transactional
def update_node_interfaces(node, data):
    """Update the interfaces attached to the node

    :param data: a dict containing commissioning data
    """
    from metadataserver.builtin_scripts.hooks import (
        parse_interfaces,
        update_interface_details,
    )

    if "network-extra" in data:
        topology_hints = data["network-extra"]["hints"]
        monitored_interfaces = data["network-extra"]["monitored-interfaces"]
        address_extra = get_address_extra(data["network-extra"]["interfaces"])
    else:
        topology_hints = None
        monitored_interfaces = []
        address_extra = {}

    current_interfaces = {
        interface.id: interface
        for interface in node.current_config.interface_set.all()
    }

    # Update the interfaces in dependency order. This make sure that the
    # parent is created or updated before the child. The order inside
    # of the sorttop result is ordered so that the modification locks that
    # postgres grabs when updating interfaces is always in the same order.
    # The ensures that multiple threads can call this method at the
    # exact same time. Without this ordering it will deadlock because
    # multiple are trying to update the same items in the database in
    # a different order.
    process_order = sorttop(get_interface_dependencies(data))
    process_order = [sorted(list(items)) for items in process_order]
    # Cache the neighbour discovery settings, since they will be used for
    # every interface on this Controller.
    discovery_mode = Config.objects.get_network_discovery_config()
    interfaces_details = parse_interfaces(node, data)
    for name in flatten(process_order):
        # Note: the interface that comes back from this call may be None,
        # if we decided not to model an interface based on what the rack
        # sent.
        interface = update_interface(
            node,
            name,
            data,
            address_extra,
            hints=topology_hints,
        )
        if interface is None:
            continue
        interface.update_discovery_state(
            discovery_mode, name in monitored_interfaces
        )
        if interface.type == INTERFACE_TYPE.PHYSICAL:
            update_interface_details(interface, interfaces_details)
        if interface.id in current_interfaces:
            del current_interfaces[interface.id]

    # Remove all the interfaces that no longer exist. We do this in reverse
    # order so the child is deleted before the parent.
    deletion_order = {}
    for nic_id, nic in current_interfaces.items():
        deletion_order[nic_id] = [
            parent.id
            for parent in nic.parents.all()
            if parent.id in current_interfaces
        ]
    deletion_order = sorttop(deletion_order)
    deletion_order = [sorted(list(items)) for items in deletion_order]
    deletion_order = reversed(list(flatten(deletion_order)))

    from metadataserver.enum import HARDWARE_SYNC_ACTIONS

    for delete_id in deletion_order:
        if node.boot_interface_id == delete_id:
            node.boot_interface = None
        _hardware_sync_network_device_notify(
            node, current_interfaces[delete_id], HARDWARE_SYNC_ACTIONS.REMOVED
        )
        current_interfaces[delete_id].delete()
    node.save()


def update_interface(node, name, data, address_extra, hints=None):
    """Update a interface.

    :param name: Name of the interface.
    :param data: Commissioning data as a dict.
    :param address_extra: Extra data about IP addresses that controller
        collects.
    :param hints: Beaconing hints that the controller collects.
    """
    network = data["networks"][name]
    if network["type"] != "broadcast":
        return None
    if network["hwaddr"] == SWITCH_OPENBMC_MAC:
        # Ignore OpenBMC interfaces on switches which all share the
        # same, hard-coded OpenBMC MAC address.
        return None
    # See LP:1939456
    if is_ipoib_mac(network["hwaddr"]):
        return None

    links = []
    for address in network["addresses"]:
        if address["scope"] != "global":
            continue
        link = address.copy()
        link.update(address_extra.get(link["address"], {}))
        links.append(link)
    # fix networks that have a /32 or /128 netmask to the closest wider known
    # subnet
    fix_link_addresses(links)

    if network["vlan"]:
        return update_vlan_interface(node, name, network, links)
    elif network["bond"] or network["bridge"]:
        return update_child_interface(node, name, network, links)
    else:
        card, port = get_card_port(name, data)
        return update_physical_interface(
            node, name, network, links, card=card, port=port, hints=hints
        )


def get_card_port(name, data):
    for card in data["resources"]["network"]["cards"]:
        for port in card.get("ports", []):
            if port["id"] == name:
                return card, port
    else:
        return None, None


def update_physical_interface(
    node, name, network, links, card=None, port=None, hints=None
):
    """Update a physical interface.

    :param name: Name of the interface.
    :param config: Interface dictionary that was parsed from
        /etc/network/interfaces on the rack controller.
    """
    from metadataserver.enum import HARDWARE_SYNC_ACTIONS

    new_vlan = None
    # In containers, for example, there will be interfaces that are
    # like physical NICs, but they don't have an actual NIC
    # associated with them. We still model them as physical NICs.
    mac_address = port["address"] if port else network["hwaddr"]
    update_fields = set()
    is_connected = network["state"] == "up"
    if port is not None:
        is_connected = is_connected and port["link_detected"]
    # If an interface with same name and different MAC exists in the
    # machine, delete it. Interface names are unique on a machine, so this
    # might be an old interface which was removed and recreated with a
    # different MAC.
    PhysicalInterface.objects.filter(
        node_config=node.current_config, name=name
    ).exclude(mac_address=mac_address).delete()
    interface, created = PhysicalInterface.objects.get_or_create(
        mac_address=mac_address,
        defaults={
            "node_config": node.current_config,
            "name": name,
            "enabled": True,
            # actual physical interfaces are to be considered non-acquired in hw sync to be preserved on release
            "acquired": not (
                node.is_commissioning()
                or (node.enable_hw_sync and port is not None)
            ),
        },
    )
    if created:
        _hardware_sync_network_device_notify(
            node, interface, HARDWARE_SYNC_ACTIONS.ADDED
        )

    if not created and interface.node_config_id != node.current_config_id:
        # MAC address was on a different node. We need to move
        # it to its new owner. In the process we delete all of its
        # current links because they are completely wrong.
        PhysicalInterface.objects.filter(id=interface.id).delete()
        return update_physical_interface(
            node, name, network, links, card=card, port=port, hints=hints
        )
    # Don't update the VLAN unless:
    # (1) The interface's VLAN wasn't previously known.
    # (2) The interface is connected
    if interface.vlan is None and is_connected:
        if hints is not None:
            new_vlan = guess_vlan_from_hints(node, name, hints)
        if new_vlan is None:
            new_vlan = guess_vlan_for_interface(node, links)
        if new_vlan is not None:
            interface.vlan = new_vlan
            update_fields.add("vlan")
    if not created:
        if interface.node_config_id != node.current_config_id:
            # MAC address was on a different node. We need to move
            # it to its new owner. In the process we delete all of its
            # current links because they are completely wrong.
            interface.ip_addresses.all().delete()
            interface.node_config = node.current_config
            update_fields.add("node_config")
        if interface.name != name:
            interface.name = name
            update_fields.add("name")
    if interface.link_connected != is_connected:
        interface.link_connected = is_connected
        update_fields.add("link_connected")

    # Update all the IP address on this interface. Fix the VLAN the
    # interface belongs to so its the same as the links.
    update_physical_links(node, interface, links, new_vlan, update_fields)
    if update_fields:
        interface.save(update_fields=list(update_fields))
    if not created:
        _hardware_sync_network_device_notify(
            node, interface, HARDWARE_SYNC_ACTIONS.UPDATED
        )
    return interface


def update_physical_links(node, interface, links, new_vlan, update_fields):
    update_ip_addresses = update_links(node, interface, links)
    linked_vlan = guess_best_vlan_from_ip_addresses(node, update_ip_addresses)
    if linked_vlan is None:
        return
    if interface.vlan != linked_vlan:
        interface.vlan = linked_vlan
        update_fields.add("vlan")


def guess_vlan_from_hints(node, ifname, hints):
    """Returns the VLAN the interface is present on based on beaconing.

    Goes through the list of hints and uses them to determine which VLAN
    the interface on this Node with the given `ifname` is on.
    """
    relevant_hints = (
        hint
        for hint in hints
        # For now, just consider hints for the interface currently being
        # processed, where beacons were sent and received without a VLAN
        # tag.
        if hint.get("ifname") == ifname
        and hint.get("vid") is None
        and hint.get("related_vid") is None
    )
    existing_vlan = None
    related_interface = None
    for hint in relevant_hints:
        hint_type = hint.get("hint")
        related_mac = hint.get("related_mac")
        related_ifname = hint.get("related_ifname")
        if hint_type in ("on_remote_network", "routable_to") and (
            related_mac is not None
        ):
            related_interface = find_related_interface(
                node, False, related_ifname, related_mac
            )
        elif hint_type in (
            "rx_own_beacon_on_other_interface",
            "same_local_fabric_as",
        ):
            related_interface = find_related_interface(
                node, True, related_ifname
            )
        # Found an interface that corresponds to the relevant hint.
        # If it has a VLAN defined, use it!
        if related_interface is not None:
            if related_interface.vlan is not None:
                existing_vlan = related_interface.vlan
                break
    return existing_vlan


def update_vlan_interface(node, name, network, links):
    """Update a VLAN interface.

    :param name: Name of the interface.
    :param network: Network settings from commissioning data.
    """
    vid = network["vlan"]["vid"]
    parent_name = network["vlan"]["lower_device"]
    parent_nic = Interface.objects.get(
        node_config=node.current_config, name=parent_name
    )
    links_vlan = get_interface_vlan_from_links(links)
    if links_vlan:
        vlan = links_vlan
        if parent_nic.vlan.fabric_id != vlan.fabric_id:
            # XXX: We should surface this error to the API and UI, since
            # it's something the user needs to fix.
            maaslog.error(
                f"Interface '{parent_nic.name}' on controller '{node.hostname}' "
                f"is not on the same fabric as VLAN interface '{name}'."
            )
        if links_vlan.vid != vid:
            maaslog.error(
                f"VLAN interface '{name}' reports VLAN {vid} "
                f"but links are on VLAN {links_vlan.vid}"
            )
    else:
        vlan = None

    from metadataserver.builtin_scripts.hooks import HARDWARE_SYNC_ACTIONS

    interface = VLANInterface.objects.filter(
        node_config=node.current_config,
        name=name,
        parents__id=parent_nic.id,
        vlan__vid=vid,
    ).first()
    if interface is None:
        if vlan is None:
            # Since no suitable VLAN is found, create a new one in the same
            # fabric as the parent interface.
            if parent_nic.vlan:
                vlan, _ = VLAN.objects.get_or_create(
                    fabric=parent_nic.vlan.fabric, vid=vid
                )
            elif network["addresses"]:  # use IP address to find VLAN
                address = network["addresses"][0]["address"]
                try:
                    subnet = Subnet.objects.get_subnet_for_ip(address)
                except Subnet.DoesNotExist:
                    pass
                else:
                    vlan, _ = VLAN.objects.get_or_create(
                        fabric=subnet.vlan.fabric, vid=vid
                    )
            if vlan is None:
                maaslog.error(
                    f"Unable to detect fabric VLAN Interface '{name}', using default"
                )
                vlan, _ = VLAN.objects.get_or_create(
                    fabric=Fabric.objects.get_default_fabric(), vid=vid
                )

        interface, created = VLANInterface.objects.get_or_create(
            node_config=node.current_config,
            name=name,
            parents=[parent_nic],
            vlan=vlan,
            defaults={"acquired": True},
        )
        _hardware_sync_network_device_notify(
            node,
            interface,
            HARDWARE_SYNC_ACTIONS.ADDED
            if created
            else HARDWARE_SYNC_ACTIONS.UPDATED,
        )
    elif vlan is not None and interface.vlan != vlan:
        interface.vlan = vlan
        interface.save()
        _hardware_sync_network_device_notify(
            node, interface, HARDWARE_SYNC_ACTIONS.UPDATED
        )

    update_links(node, interface, links, force_vlan=True)
    return interface


def update_child_interface(node, name, network, links):
    """Update a child interface.

    :param name: Name of the interface.
    :param network: Network settings from commissioning data.
    """
    if network["bridge"]:
        parents = network["bridge"]["upper_devices"]
        child_type = BridgeInterface
    elif network["bond"]:
        parents = network["bond"]["lower_devices"]
        child_type = BondInterface
    else:
        raise RuntimeError(f"Unknown child interface: {network}")
    # Get all the parent interfaces for this interface. All the parents
    # should exists because of the order the links are processed.
    parent_nics = Interface.objects.get_interfaces_on_node_by_name(
        node, parents
    )

    # Ignore most child interfaces that don't have parents. MAAS won't know
    # what to do with them since they can't be connected to a fabric.
    # Bridges are an exception since some MAAS demo/test environments
    # contain virtual bridges.
    if len(parent_nics) == 0 and not network["bridge"]:
        return None

    mac_address = network["hwaddr"]
    interface = child_type.objects.get_or_create_on_node(
        node,
        name,
        mac_address,
        parent_nics,
        acquired=True,
    )

    found_vlan = configure_vlan_from_links(node, interface, parent_nics, links)

    # Update all the IP address on this interface. Fix the VLAN the
    # interface belongs to so its the same as the links and all parents to
    # be on the same VLAN.
    update_ip_addresses = update_links(
        node, interface, links, use_interface_vlan=found_vlan
    )
    update_parent_vlans(node, interface, parent_nics, update_ip_addresses)
    return interface


def update_parent_vlans(node, interface, parent_nics, update_ip_addresses):
    """Given the specified interface model object, the specified list of
    parent interfaces, and the specified list of static IP addresses,
    update the parent interfaces to correspond to the VLAN found on the
    subnet the IP address is allocated from.

    If a static IP address is allocated, give preferential treatment to
    the VLAN that IP address resides on.
    """
    linked_vlan = guess_best_vlan_from_ip_addresses(node, update_ip_addresses)
    if linked_vlan is not None:
        interface.vlan = linked_vlan
        interface.save()
        for parent_nic in parent_nics:
            if parent_nic.vlan_id != linked_vlan.id:
                parent_nic.vlan = linked_vlan
                parent_nic.save()


def auto_vlan_creation(node) -> bool:
    if node.is_controller:
        # Always create controller's vlans
        return True

    if node.status == NODE_STATUS.DEPLOYED:
        # don't create empty vlan/fabric for interfaces discovered by HW sync,
        # they cannot be used.
        return False

    return Config.objects.get_config("auto_vlan_creation", True)


def guess_vlan_for_interface(node, links):
    # Make sure that the VLAN on the interface is correct. When
    # links exists on this interface we place it into the correct
    # VLAN. If it cannot be determined and its a new interface it
    # gets placed on its own fabric.
    new_vlan = get_interface_vlan_from_links(links)
    if new_vlan is None and auto_vlan_creation(node):
        # If the default VLAN on the default fabric has no interfaces
        # associated with it, the first interface will be placed there
        # (rather than creating a new fabric).
        default_vlan = VLAN.objects.get_default_vlan()
        interfaces_on_default_vlan = Interface.objects.filter(
            vlan=default_vlan
        ).exists()
        if not interfaces_on_default_vlan:
            new_vlan = default_vlan
        else:
            new_fabric = Fabric.objects.create()
            new_vlan = new_fabric.get_default_vlan()
    return new_vlan


def configure_vlan_from_links(node, interface, parent_nics, links):
    """Attempt to configure the interface VLAN based on the links and
    connected subnets. Returns True if the VLAN was configured; otherwise,
    returns False."""
    # Make sure that the VLAN on the interface is correct. When
    # links exists on this interface we place it into the correct
    # VLAN. If it cannot be determined it is placed on the same fabric
    # as its first parent interface.
    vlan = get_interface_vlan_from_links(links)
    if not vlan and parent_nics:
        # Not connected to any known subnets. We add it to the same
        # VLAN as its first parent.
        interface.vlan = parent_nics[0].vlan
        interface.save()
        return True
    elif vlan:
        interface.vlan = vlan
        interface.save()
        return True
    return False


def find_related_interface(
    node, own_interface: bool, related_ifname: str, related_mac: str = None
):
    """Returns a related interface matching the specified criteria.

    :param own_interface: if True, only search for "own" interfaces.
        (That is, interfaces belonging to the current node.)
    :param related_ifname: The name of the related interface to find.
    :param related_mac: The MAC address of the related interface to find.
    :return: the related interface, or None if one could not be found.
    """
    filter_args = dict()
    if related_mac is not None:
        filter_args["mac_address"] = related_mac
    if own_interface:
        filter_args["node_config"] = node.current_config
    related_interface = PhysicalInterface.objects.filter(**filter_args).first()
    if related_interface is None and related_mac is not None:
        # Couldn't find a physical interface; it could be a private
        # bridge.
        filter_args["name"] = related_ifname
        related_interface = BridgeInterface.objects.filter(
            **filter_args
        ).first()
    return related_interface


def get_interface_vlan_from_links(links):
    """Return the VLAN for an interface from its links.

    It's assumed that all subnets for VLAN links are on the same VLAN.

    This returns None if no VLAN is found.
    """
    cidrs = {
        str(IPNetwork(f"{link['address']}/{link['netmask']}").cidr)
        for link in links
    }
    return VLAN.objects.filter(subnet__cidr__in=cidrs).first()


def get_alloc_type_from_ip_addresses(node, alloc_type, ip_addresses):
    """Return IP address from `ip_addresses` that is first
    with `alloc_type`."""
    for ip_address in ip_addresses:
        if alloc_type == ip_address.alloc_type:
            return ip_address
    return None


def guess_best_vlan_from_ip_addresses(node, ip_addresses):
    """Return the first VLAN for a STICKY IP address in `ip_addresses`."""
    second_best = None
    for ip_address in ip_addresses:
        if ip_address.alloc_type == IPADDRESS_TYPE.STICKY:
            return ip_address.subnet.vlan
        elif ip_address.alloc_type == IPADDRESS_TYPE.DISCOVERED:
            second_best = ip_address.subnet.vlan
    return second_best


def update_links(
    node, interface, links, force_vlan=False, use_interface_vlan=True
):
    """Update the links on `interface`."""
    interface.ip_addresses.filter(
        alloc_type=IPADDRESS_TYPE.DISCOVERED
    ).delete()
    current_ip_addresses = set(interface.ip_addresses.all())
    updated_ip_addresses = set()
    if use_interface_vlan and interface.vlan is not None:
        vlan = interface.vlan
    elif links:
        fabric = Fabric.objects.create()
        vlan = fabric.get_default_vlan()
        interface.vlan = vlan
        interface.save()

    def get_or_create_subnet(ip_network, vlan):
        """Get or create the subnet for the IPNetwork.

        If created it will be added to the VLAN on the interface.
        """
        if (ip_network.version, ip_network.prefixlen) in ((4, 32), (6, 128)):
            # if this network has a full netmask, look for the smallest
            # existing subnet which contains it.
            subnet = (
                Subnet.objects.annotate(
                    contains_net=RawSQL("cidr >>= %s", [str(ip_network)])
                )
                .filter(contains_net=True)
                .order_by("-cidr")
                .first()
            )
            if subnet:
                return subnet

        cidr = str(ip_network.cidr)
        subnet, _ = Subnet.objects.get_or_create(
            cidr=cidr,
            defaults={"name": cidr, "vlan": vlan},
        )
        return subnet

    for link in links:
        if link.get("mode") == "dhcp":
            dhcp_address = get_alloc_type_from_ip_addresses(
                node, IPADDRESS_TYPE.DHCP, current_ip_addresses
            )
            if dhcp_address is None:
                dhcp_address = StaticIPAddress.objects.create(
                    alloc_type=IPADDRESS_TYPE.DHCP, ip=None, subnet=None
                )
                dhcp_address.save()
                interface.ip_addresses.add(dhcp_address)
            else:
                current_ip_addresses.remove(dhcp_address)
            if "address" in link:
                # DHCP IP address was discovered. Add it as a discovered
                # IP address.
                ip_network = IPNetwork(f"{link['address']}/{link['netmask']}")
                ip_addr = str(ip_network.ip)
                subnet = get_or_create_subnet(ip_network, vlan)

                # Make sure that the subnet is on the same VLAN as the
                # interface.
                if force_vlan and subnet.vlan_id != interface.vlan_id:
                    maaslog.error(
                        f"Unable to update IP address '{ip_addr}' assigned "
                        f"to interface '{interface.name}' on controller '{node.hostname}'. "
                        f"Subnet '{subnet.name}' for IP address is not on "
                        f"VLAN '{subnet.vlan.fabric.name}.{subnet.vlan.vid}'."
                    )
                    continue

                # Create the DISCOVERED IP address.
                ip_address, _ = StaticIPAddress.objects.update_or_create(
                    ip=ip_addr,
                    defaults={
                        "alloc_type": IPADDRESS_TYPE.DISCOVERED,
                        "subnet": subnet,
                    },
                )
                interface.ip_addresses.add(ip_address)
            updated_ip_addresses.add(dhcp_address)
        else:
            ip_network = IPNetwork(f"{link['address']}/{link['netmask']}")
            ip_addr = str(ip_network.ip)
            subnet = get_or_create_subnet(ip_network, vlan)

            # Make sure that the subnet is on the same VLAN as the
            # interface.
            if force_vlan and subnet.vlan_id != interface.vlan_id:
                maaslog.error(
                    f"Unable to update IP address '{str(ip_network)}' assigned "
                    f"to interface '{interface.name}' on controller '{node.hostname}'. "
                    f"Subnet '{subnet.name}' for IP address is not on "
                    f"VLAN '{subnet.vlan.fabric.name}.{subnet.vlan.vid}'."
                )
                continue

            # Update the gateway on the subnet if one is not set.
            if (
                subnet.gateway_ip is None
                and link.get("gateway")
                and IPAddress(link["gateway"]) in subnet.get_ipnetwork()
            ):
                subnet.gateway_ip = link["gateway"]
                subnet.save()

            address_type = (
                IPADDRESS_TYPE.DISCOVERED
                if node.is_commissioning()
                else IPADDRESS_TYPE.STICKY
            )
            # IP address is not assigned to this interface. Get or
            # create that IP address.
            ip_address, created = StaticIPAddress.objects.update_or_create(
                ip=ip_addr,
                defaults={
                    "alloc_type": address_type,
                    "subnet": subnet,
                },
            )
            if not created:
                current_ip_addresses.discard(ip_address)

            # Update the properties and make sure all interfaces
            # assigned to the address belong to this node.
            for attached_nic in ip_address.interface_set.all():
                config = attached_nic.node_config
                if config is None or config.node_id != node.id:
                    attached_nic.ip_addresses.remove(ip_address)

            # Add this IP address to the interface.
            interface.ip_addresses.add(ip_address)
            updated_ip_addresses.add(ip_address)

    # Remove all the current IP address that no longer apply to this
    # interface.
    for ip_address in current_ip_addresses:
        interface.unlink_ip_address(ip_address)

    return updated_ip_addresses
