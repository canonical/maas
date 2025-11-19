# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Respond to DNSData changes."""

from django.db.models.signals import post_delete, post_save

from maascommon.enums.dns import DnsUpdateAction
from maasserver.models import DNSPublication, RegionRackRPCConnection
from maasserver.utils.signals import SignalsManager

signals = SignalsManager()


def post_save_dns_publication(sender, instance, created, **kwargs):
    num_connections = RegionRackRPCConnection.objects.filter(
        rack_controller=instance.rack_controller
    ).count()

    if num_connections == 1:
        # First connection of the rack controller requires the DNS to
        # be reloaded for the internal MAAS domain
        DNSPublication.objects.create_for_config_update(
            source=f"rack controller {instance.rack_controller.hostname} connected",
            action=DnsUpdateAction.RELOAD,
        )


def post_delete_dns_publication(sender, instance, **kwargs):
    num_connections = RegionRackRPCConnection.objects.filter(
        rack_controller=instance.rack_controller
    ).count()

    if num_connections == 0:
        # No connections of the rack controller requires the DNS to be
        # reloaded for the internal MAAS domain.
        DNSPublication.objects.create_for_config_update(
            source=f"rack controller {instance.rack_controller.hostname} disconnected",
            action=DnsUpdateAction.RELOAD,
        )


signals.watch(
    post_save, post_save_dns_publication, sender=RegionRackRPCConnection
)
signals.watch(
    post_delete, post_delete_dns_publication, sender=RegionRackRPCConnection
)

# Enable all signals by default.
signals.enable()
