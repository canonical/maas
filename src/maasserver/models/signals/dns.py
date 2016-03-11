# Copyright 2012-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""DNS management module: connect DNS tasks with signals."""

__all__ = [
    "signals",
]

from django.db.models.signals import (
    m2m_changed,
    post_delete,
    post_save,
)
from maasserver.enum import RDNS_MODE
from maasserver.models import (
    DNSData,
    DNSResource,
    Domain,
    Interface,
    Node,
    StaticIPAddress,
    Subnet,
)
from maasserver.utils.signals import SignalsManager
from netaddr import IPNetwork


signals = SignalsManager()


def dns_post_save_Domain(sender, instance, created, **kwargs):
    """Create or update DNS zones as needed for this domain."""
    from maasserver.dns.config import (
        dns_add_domains,
        dns_update_all_zones,
        )
    # if we created the domain, then we can just add it.
    if created:
        dns_add_domains({instance})
    else:
        dns_update_all_zones()

signals.watch(
    post_save, dns_post_save_Domain,
    sender=Domain)


def dns_post_save_StaticIPAddress(sender, instance, created, **kwargs):
    """Create or update DNS zones as needed for this address."""
    from maasserver.dns.config import dns_update_all_zones
    # if we created the StaticIPAddress, then there's actually nothing to do,
    # since there are no linkages.  If it was updated, we have no idea what may
    # have changed, so update all the DNS zones.
    if not created:
        dns_update_all_zones()

signals.watch(
    post_save, dns_post_save_StaticIPAddress,
    sender=StaticIPAddress)


def dns_m2m_changed_Interface_m2m(sender, instance, action, reverse,
                                  model, pk_set, **kwargs):
    """Create or update DNS zones as needed for this interface/address."""
    from maasserver.dns.config import (
        dns_update_all_zones,
        dns_update_domains,
        dns_update_subnets,
        )
    if action == 'post_remove' or action == 'post_clear':
        dns_update_all_zones()
    elif action == 'post_add':
        if reverse:
            # The StaticIPAddress is being updated by adding new interfaces
            domains = set(
                iface.node.domain
                for iface in model.objects.filter(
                    id__in=pk_set).exclude(
                    node__isnull=True).exclude(node__domain__isnull=True))
            dns_update_domains(domains)
            dns_update_subnets({instance.subnet})
        else:
            # The Interface is the one being updated.
            if instance.node is not None and instance.node.domain is not None:
                dns_update_domains({instance.node.domain})
            subnets = set(
                sip.subnet
                for sip in model.objects.filter(
                    id__in=pk_set).exclude(subnet__isnull=True))
            dns_update_subnets(subnets)

signals.watch(
    m2m_changed, dns_m2m_changed_Interface_m2m,
    sender=Interface.ip_addresses.through)


def dns_m2m_changed_DNSResource_m2m(sender, instance, action, reverse,
                                    model, pk_set, **kwargs):
    """Create or update DNS zones as needed for this dnsresource/address."""
    from maasserver.dns.config import (
        dns_update_all_zones,
        dns_update_domains,
        dns_update_subnets,
        )
    if action == 'post_remove' or action == 'post_clear':
        dns_update_all_zones()
    elif action == 'post_add':
        if reverse:
            # The StaticIPAddress is being updated by adding new DNSResource
            domains = set(
                res.domain
                for res in model.objects.filter(id__in=pk_set))
            dns_update_domains(domains)
            dns_update_subnets({instance.subnet})
        else:
            # The DNSResource is the one being updated.
            dns_update_domains({instance.domain})
            subnets = set(
                sip.subnet
                for sip in model.objects.filter(
                    id__in=pk_set).exclude(subnet__isnull=True))
            dns_update_subnets(subnets)

signals.watch(
    m2m_changed, dns_m2m_changed_DNSResource_m2m,
    sender=DNSResource.ip_addresses.through)


def dns_post_save_DNSResource(sender, instance, created, **kwargs):
    """Create or update DNS zones as needed for this domain."""
    from maasserver.dns.config import (
        dns_update_domains,
        dns_update_all_zones,
        )
    # if we just created the DNSResource, then there won't be any ip_addresses,
    # because those have to be added after the save happens.
    if created:
        dns_update_domains({instance.domain})
    else:
        dns_update_all_zones()

signals.watch(
    post_save, dns_post_save_DNSResource,
    sender=DNSResource)


def dns_post_save_DNSData(sender, instance, created, **kwargs):
    """Create or update DNS zones as needed for this domain."""
    from maasserver.dns.config import (
        dns_update_domains,
        dns_update_all_zones,
        )
    # if we created the DNSData, then we can just update the domain.
    if created:
        dns_update_domains({instance.dnsresource.domain})
    else:
        dns_update_all_zones()

signals.watch(
    post_save, dns_post_save_DNSData,
    sender=DNSData)


def dns_post_save_Subnet(sender, instance, created, **kwargs):
    """Create or update DNS zones related to the saved nodegroupinterface."""
    from maasserver.dns.config import (
        dns_update_all_zones,
        dns_add_subnets,
        dns_update_subnets,
        )
    # If we created it, just add the zone for the subnet, and update the parent
    # subnet if this is a subnet requiring rfc2317 glue and we have a parent
    # subnet.
    # Otherwise, rebuild the world, since we don't know but what the admin
    # moved a subnet.
    if created:
        dns_add_subnets({instance})
        net = IPNetwork(instance.cidr)
        if ((net.version == 4 and net.prefixlen > 24 or net.prefixlen > 124)
                and instance.rdns_mode == RDNS_MODE.RFC2317):
            parent = instance.get_smallest_enclosing_sane_subnet()
            if parent is not None:
                dns_update_subnets({parent})
    else:
        dns_update_all_zones()

signals.watch(
    post_save, dns_post_save_Subnet,
    sender=Subnet)


def dns_post_delete_Node(sender, instance, **kwargs):
    """When a Node is deleted, update the Node's zone file."""
    from maasserver.dns import config as dns_config
    dns_config.dns_update_by_node(instance)

signals.watch(
    post_delete, dns_post_delete_Node,
    sender=Node)


def dns_post_edit_Node_hostname_and_domain(instance, old_values, **kwargs):
    """When a Node has been flagged, update the related zone."""
    from maasserver.dns import config as dns_config
    dns_config.dns_update_by_node(instance)

signals.watch_fields(
    dns_post_edit_Node_hostname_and_domain, Node, ['hostname', 'domain_id'])


def dns_setting_changed(sender, instance, created, **kwargs):
    from maasserver.dns.config import dns_update_all_zones
    dns_update_all_zones()


def dns_kms_setting_changed(sender, instance, created, **kwargs):
    from maasserver.models.domain import dns_kms_setting_changed
    dns_kms_setting_changed()


# Changes to upstream_dns.
signals.watch_config(dns_setting_changed, "upstream_dns")
signals.watch_config(dns_setting_changed, "default_dns_ttl")

# Changes to windows_kms_host.
signals.watch_config(dns_kms_setting_changed, "windows_kms_host")


# Enable all signals by default.
signals.enable()
