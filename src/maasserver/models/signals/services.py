# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Respond to RPC connection changes."""

from django.db.models.signals import post_delete, post_save

from maasserver.models.node import RackController
from maasserver.models.regioncontrollerprocess import RegionControllerProcess
from maasserver.models.regionrackrpcconnection import RegionRackRPCConnection
from maasserver.models.service import Service
from maasserver.utils.signals import SignalsManager

signals = SignalsManager()


def update_rackd_status(sender, instance, **kwargs):
    """Update status of the rackd service for the rack controller the
    RPC connection was added or removed.
    """
    Service.objects.create_services_for(instance.rack_controller)
    instance.rack_controller.update_rackd_status()


signals.watch(post_save, update_rackd_status, sender=RegionRackRPCConnection)

signals.watch(post_delete, update_rackd_status, sender=RegionRackRPCConnection)


def update_all_rackd_status(sender, instance, **kwargs):
    """Update status of all rackd services when a region controller process is
    added or removed.
    """
    for rack_controller in RackController.objects.all():
        Service.objects.create_services_for(rack_controller)
        rack_controller.update_rackd_status()


signals.watch(
    post_save, update_all_rackd_status, sender=RegionControllerProcess
)

signals.watch(
    post_delete, update_all_rackd_status, sender=RegionControllerProcess
)

# Enable all signals by default.
signals.enable()
