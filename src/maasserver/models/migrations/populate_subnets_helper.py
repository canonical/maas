# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Migration to populate subnets.

WARNING: Although these methods will become obsolete very quickly, they
cannot be removed, since they are used by the 0145_populate_subnets
DataMigration. (changing them might also be futile unless a customer
restores from a backup, since any bugs that occur will have already occurred,
and this code will not be executed again.)

Note: Each helper must have its dependencies on any model classes injected,
since the migration environment is a skeletal replication of the 'real'
database model. So each function takes as parameters the model classes it
requires. Importing from the model is not allowed here. (but the unit tests
do it, to ensure that the migrations meet validation requirements.)
"""

from netaddr import IPNetwork


# Need to replicate this enum here so it's "frozen in time" for this migration.
class _NODEGROUPINTERFACE_MANAGEMENT:
    UNMANAGED = 0
    DHCP = 1
    DHCP_AND_DNS = 2


def _get_cidr(ip, subnet_mask):
    """Returns a unicode CIDR for the specified (ip, subnet mask) tuple."""
    if subnet_mask:
        return str(IPNetwork(f"{ip}/{subnet_mask}").cidr)

    return None


def _get_cidr_for_nodegroupinterface(ngi):
    """Returns a unicode CIDR for the specified NodeGroupInterface."""
    return _get_cidr(ngi.ip, ngi.subnet_mask)


def _get_cidr_for_network(network):
    """Returns a unicode CIDR for the specified Network."""
    return _get_cidr(network.ip, network.netmask)


def _migrate_networks_forward(
    now, Network, Subnet, VLAN, default_fabric, default_space, default_vlan
):
    """Creates Subnets and VLANs matching the specified input Network
    objects.
    """
    for network in Network.objects.all():
        cidr = _get_cidr_for_network(network)
        try:
            subnet = Subnet.objects.get(cidr=cidr)
        except Subnet.DoesNotExist:
            subnet = Subnet()
            subnet.cidr = cidr
            subnet.name = cidr
            subnet.created = now
        subnet.gateway_ip = network.default_gateway
        subnet.space = default_space

        # Find or create the specified VLAN
        if network.vlan_tag is not None and network.vlan_tag > 0:
            try:
                vlan = VLAN.objects.get(
                    vid=network.vlan_tag, fabric=default_fabric
                )
            except VLAN.DoesNotExist:
                vlan = VLAN(vid=network.vlan_tag, fabric=default_fabric)
                vlan.name = "vlan%d" % network.vlan_tag
                vlan.created = now
                vlan.updated = now
                vlan.save()
            subnet.vlan = vlan
        else:
            subnet.vlan = default_vlan

        if network.dns_servers is not None:
            subnet.dns_servers = network.dns_servers.split()

        if subnet.name is not None and subnet.name != "":
            subnet.name = network.name

        subnet.updated = now
        subnet.save()


def _migrate_nodegroupinterfaces_forward(
    now, NodeGroupInterface, Subnet, default_space, default_vlan
):
    """Creates Subnet objects based on the given NodeGroupInterfaces.

    Requires _migrate_networks_forward() to have already been called.
    """

    # Need to do this three times, in a specific order. (Since we overwrite the
    # information in each created Subnet, and we want to trust
    # currently-UNMANAGED networks the *least*, followed by DHCP-only networks,
    # and finally put the most trust in DHCP-and-DNS managed clusters.
    management_types_priority = [
        _NODEGROUPINTERFACE_MANAGEMENT.UNMANAGED,
        _NODEGROUPINTERFACE_MANAGEMENT.DHCP,
        _NODEGROUPINTERFACE_MANAGEMENT.DHCP_AND_DNS,
    ]
    for management in management_types_priority:
        for ngi in NodeGroupInterface.objects.filter(management=management):
            _create_subnet_from_nodegroupinterface(
                now, ngi, Subnet, default_space, default_vlan
            )


def _create_subnet_from_nodegroupinterface(
    now, ngi, Subnet, default_space, default_vlan
):
    cidr = _get_cidr_for_nodegroupinterface(ngi)
    if cidr is not None:
        try:
            subnet = Subnet.objects.get(cidr=cidr)
        except Subnet.DoesNotExist:
            subnet = Subnet()
            subnet.name = cidr
            # VLAN might have been populated by the migration from Network.
            subnet.vlan = default_vlan
            subnet.created = now
        subnet.cidr = cidr
        subnet.space = default_space
        subnet.updated = now
        subnet.gateway_ip = ngi.router_ip
        subnet.save()
    else:
        subnet = None
    ngi.subnet = subnet
    ngi.updated = now
    ngi.save()
