# Copyright 2012-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""DNS management module: connect DNS tasks with signals."""

__all__ = [
    "signals",
]

from django.db.models.signals import (
    post_delete,
    post_save,
)
from maasserver.enum import NODEGROUPINTERFACE_MANAGEMENT
from maasserver.models import (
    DNSData,
    DNSResource,
    Domain,
    Node,
    NodeGroupInterface,
    Subnet,
)
from maasserver.utils.signals import SignalsManager


signals = SignalsManager()


def dns_post_save_Domain(sender, instance, created, **kwargs):
    """Create or update DNS zones as needed for this domain."""
    from maasserver.dns.config import (
        dns_add_domains,
        dns_update_all_zones,
        )
    # if we created the domain, then we can just add it.
    if created:
        dns_add_domains([instance])
    else:
        dns_update_all_zones()

signals.watch(
    post_save, dns_post_save_Domain,
    sender=Domain)


def dns_post_save_DNSResource(sender, instance, created, **kwargs):
    """Create or update DNS zones as needed for this domain."""
    from maasserver.dns.config import (
        dns_update_domains,
        dns_update_all_zones,
        )
    # if we created the DNSResource, then we can just update the domain.
    if created:
        dns_update_domains([instance.domain])
        # if we just created the DNSResource, then there won't be any
        # ip_addresses, because those have to be added after the save happens.
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
        dns_update_domains([instance.dnsresource.domain])
    else:
        dns_update_all_zones()

signals.watch(
    post_save, dns_post_save_DNSData,
    sender=DNSData)


# XXX rvb 2012-09-12: This is only needed because we use that
# information to pre-populate the zone file.  Once we stop doing that,
# this can be removed.
def dns_post_save_NodeGroupInterface(sender, instance, created, **kwargs):
    """Create or update DNS zones related to the saved nodegroupinterface."""
    from maasserver.dns.config import (
        dns_update_all_zones,
        dns_add_subnets,
        )
    if created:
        dns_add_subnets(instance.subnet)
    else:
        dns_update_all_zones()

signals.watch(
    post_save, dns_post_save_NodeGroupInterface,
    sender=NodeGroupInterface)


def dns_post_save_Subnet(sender, instance, created, **kwargs):
    """Create or update DNS zones related to the saved nodegroupinterface."""
    from maasserver.dns.config import (
        dns_update_all_zones,
        dns_add_subnets,
        )
    # We don't know but what the admin moved a subnet, so we need to regenerate
    # the world.
    # if we created it, just add it.  Otherwise, rebuild the world.
    if created:
        dns_add_subnets([instance])
    else:
        dns_update_all_zones()

signals.watch(
    post_save, dns_post_save_Subnet,
    sender=Subnet)


def dns_post_edit_management_NodeGroupInterface(instance, old_values, deleted):
    """Delete DNS zones related to the interface."""
    from maasserver.dns.config import dns_update_all_zones
    [old_field] = old_values
    if old_field == NODEGROUPINTERFACE_MANAGEMENT.DHCP_AND_DNS:
        # Force the dns config to be written as this might have been
        # triggered by the last DNS-enabled interface being deleted
        # or switched off (i.e. management set to DHCP or UNMANAGED).
        dns_update_all_zones(force=True)

signals.watch_fields(
    dns_post_edit_management_NodeGroupInterface,
    NodeGroupInterface, ['management'], delete=True)


def dns_post_delete_Node(sender, instance, **kwargs):
    """When a Node is deleted, update the Node's zone file."""
    from maasserver.dns import config as dns_config
    dns_config.dns_update_by_node(instance)

signals.watch(
    post_delete, dns_post_delete_Node,
    sender=Node)


def dns_post_edit_hostname_Node(instance, old_values, **kwargs):
    """When a Node has been flagged, update the related zone."""
    from maasserver.dns import config as dns_config
    dns_config.dns_update_by_node(instance)

signals.watch_fields(
    dns_post_edit_hostname_Node, Node, ['hostname', 'domain_id'])


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
