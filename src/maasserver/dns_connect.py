# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""DNS management module: connect DNS tasks with signals."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    ]


from django.db.models.signals import (
    post_delete,
    post_save,
    )
from django.dispatch import receiver
from maasserver.enum import NODEGROUPINTERFACE_MANAGEMENT
from maasserver.models import (
    Config,
    Node,
    NodeGroup,
    NodeGroupInterface,
    )
from maasserver.signals import connect_to_field_change


@receiver(post_save, sender=NodeGroup)
def dns_post_save_NodeGroup(sender, instance, created, **kwargs):
    """Create or update DNS zones related to the saved nodegroup."""
    from maasserver.dns import write_full_dns_config, add_zone
    if created:
        add_zone(instance)
    else:
        write_full_dns_config()


# XXX rvb 2012-09-12: This is only needed because we use that
# information to pre-populate the zone file.  Once we stop doing that,
# this can be removed.
@receiver(post_save, sender=NodeGroupInterface)
def dns_post_save_NodeGroupInterface(sender, instance, created, **kwargs):
    """Create or update DNS zones related to the saved nodegroupinterface."""
    from maasserver.dns import write_full_dns_config, add_zone
    if created:
        add_zone(instance.nodegroup)
    else:
        write_full_dns_config()


def dns_post_edit_management_NodeGroupInterface(instance, old_field, deleted):
    """Delete DNS zones related to the interface."""
    from maasserver.dns import write_full_dns_config
    if old_field == NODEGROUPINTERFACE_MANAGEMENT.DHCP_AND_DNS:
        # Force the dns config to be written as this might have been
        # triggered by the last DNS-enabled interface being deleted
        # or switched off (i.e. management set to DHCP or UNMANAGED).
        write_full_dns_config(force=True)


connect_to_field_change(
    dns_post_edit_management_NodeGroupInterface,
    NodeGroupInterface, 'management', delete=True)


@receiver(post_delete, sender=Node)
def dns_post_delete_Node(sender, instance, **kwargs):
    """When a Node is deleted, update the Node's zone file."""
    try:
        from maasserver.dns import change_dns_zones
        change_dns_zones(instance.nodegroup)
    except NodeGroup.DoesNotExist:
        # If this Node is being deleted because the whole NodeGroup
        # has been deleted, no need to update the zone file because
        # this Node got removed.
        pass


def dns_post_edit_hostname_Node(instance, old_field, **kwargs):
    """When a Node has been flagged, update the related zone."""
    from maasserver.dns import change_dns_zones
    change_dns_zones(instance.nodegroup)


connect_to_field_change(dns_post_edit_hostname_Node, Node, 'hostname')


def upstream_dns_changed(sender, instance, created, **kwargs):
    from maasserver.dns import write_full_dns_config
    write_full_dns_config()


Config.objects.config_changed_connect("upstream_dns", upstream_dns_changed)
