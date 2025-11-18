# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Respond to VLAN changes."""

from django.db.models.signals import post_delete, post_save

from maascommon.workflows.dhcp import (
    CONFIGURE_DHCP_WORKFLOW_NAME,
    ConfigureDHCPParam,
)
from maasserver.models import RackController, VLAN
from maasserver.utils.orm import post_commit_do
from maasserver.utils.signals import SignalsManager
from maasserver.workflow import start_workflow
from maastemporalworker.worker import REGION_TASK_QUEUE

signals = SignalsManager()


def post_save_dhcp_workflow(sender, instance, created, **kwargs):
    if created:
        needs_dhcp_update = instance.dhcp_on or instance.relay_vlan_id
        if needs_dhcp_update:
            param = ConfigureDHCPParam(system_ids=[], vlan_ids=[instance.id])
            post_commit_do(
                start_workflow,
                workflow_name=CONFIGURE_DHCP_WORKFLOW_NAME,
                param=param,
                task_queue=REGION_TASK_QUEUE,
            )


def post_update_dhcp_workflow(instance, old_values, **kwargs):
    [
        old_dhcp_on,
        old_relay_vlan_id,
        old_primary_rack_id,
        old_secondary_rack_id,
        old_mtu,
    ] = old_values

    if (
        not old_dhcp_on
        and not instance.dhcp_on
        and not old_relay_vlan_id
        and not instance.relay_vlan_id
    ):
        # If DHCP was off and is still off, and there is no relay VLAN involved, nothing to do
        return

    vlan_ids = []
    rack_controller_system_ids = []

    if old_relay_vlan_id != instance.relay_vlan_id:
        if old_relay_vlan_id:
            # The old relay VLAN needs updating
            vlan_ids.append(old_relay_vlan_id)
        if instance.relay_vlan_id:
            # The new relay VLAN needs updating, the DHCP workflow will figure out what agents needs to be updated..
            vlan_ids.append(instance.id)
    else:
        # Include all the old/new rack controllers
        rack_controller_system_ids += RackController.objects.filter(
            id__in={
                old_primary_rack_id,
                instance.primary_rack_id,
                old_secondary_rack_id,
                instance.secondary_rack_id,
            }
        ).values_list("system_id", flat=True)

        vlan_ids.append(instance.id)

    param = ConfigureDHCPParam(
        system_ids=rack_controller_system_ids, vlan_ids=vlan_ids
    )
    post_commit_do(
        start_workflow,
        workflow_name=CONFIGURE_DHCP_WORKFLOW_NAME,
        param=param,
        task_queue=REGION_TASK_QUEUE,
    )


def post_delete_dhcp_workflow(sender, instance, **kwargs):
    vlan_ids = []
    rack_controller_system_ids = []
    if instance.dhcp_on:
        # If DHCP was enabled on this VLAN, update all associated rack controllers
        if instance.primary_rack_id:
            rack_controller_system_ids.append(instance.primary_rack.system_id)
        if instance.secondary_rack_id:
            rack_controller_system_ids.append(
                instance.secondary_rack.system_id
            )
    elif instance.relay_vlan_id:
        # Just update the relay vlan
        vlan_ids.append(instance.relay_vlan_id)
    else:
        return

    post_commit_do(
        start_workflow,
        workflow_name=CONFIGURE_DHCP_WORKFLOW_NAME,
        param=ConfigureDHCPParam(
            vlan_ids=vlan_ids, system_ids=rack_controller_system_ids
        ),
        task_queue=REGION_TASK_QUEUE,
    )


signals.watch(post_save, post_save_dhcp_workflow, sender=VLAN)
signals.watch_fields(
    post_update_dhcp_workflow,
    VLAN,
    [
        "dhcp_on",
        "relay_vlan_id",
        "primary_rack_id",
        "secondary_rack_id",
        "mtu",
    ],
    delete=False,
)
signals.watch(post_delete, post_delete_dhcp_workflow, sender=VLAN)

# Enable all signals by default.
signals.enable()
