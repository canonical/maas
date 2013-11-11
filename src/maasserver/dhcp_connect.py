# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""DHCP management module: connect DHCP tasks with signals."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    ]


from django.db.models.signals import post_save
from django.dispatch import receiver
from maasserver.models import (
    Config,
    NodeGroup,
    NodeGroupInterface,
    )
from maasserver.signals import connect_to_field_change


@receiver(post_save, sender=NodeGroupInterface)
def dhcp_post_save_NodeGroupInterface(sender, instance, created, **kwargs):
    """Update the DHCP config related to the saved nodegroupinterface."""
    # Circular import.
    from maasserver.dhcp import configure_dhcp
    configure_dhcp(instance.nodegroup)


def dhcp_post_edit_status_NodeGroup(instance, old_field, **kwargs):
    """The status of a NodeGroup changed."""
    # This could be optimized a bit by detecting if the status change is
    # actually a change from 'do not manage DHCP' to 'manage DHCP'.
    # Circular import.
    from maasserver.dhcp import configure_dhcp
    configure_dhcp(instance)


connect_to_field_change(dhcp_post_edit_status_NodeGroup, NodeGroup, 'status')


def ntp_server_changed(sender, instance, created, **kwargs):
    """The ntp_server config item changed, so write new DHCP configs."""
    from maasserver.dhcp import configure_dhcp
    for nodegroup in NodeGroup.objects.all():
        configure_dhcp(nodegroup)


Config.objects.config_changed_connect("ntp_server", ntp_server_changed)
