# Copyright 2015-2017 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Respond to node changes."""

__all__ = [
    "signals",
]

from django.db.models.signals import (
    post_init,
    post_save,
    pre_delete,
    pre_save,
)
from maasserver.clusterrpc.pods import decompose_machine
from maasserver.enum import (
    BMC_TYPE,
    NODE_STATUS,
    NODE_TYPE,
)
from maasserver.models import (
    Controller,
    Device,
    Machine,
    Node,
    RackController,
    RegionController,
    Service,
)
from maasserver.rpc import getClientFromIdentifiers
from maasserver.utils.signals import SignalsManager
from metadataserver.models.nodekey import NodeKey
from provisioningserver.drivers.pod import Capabilities
from provisioningserver.utils.twisted import asynchronous


NODE_CLASSES = [
    Node,
    Machine,
    Device,
    Controller,
    RackController,
    RegionController,
]

signals = SignalsManager()


def post_init_store_previous_status(sender, instance, **kwargs):
    """Store the pre_save status of the instance."""
    instance.__previous_status = instance.status


for klass in NODE_CLASSES:
    signals.watch(
        post_init, post_init_store_previous_status, sender=klass)


def pre_save_update_status(sender, instance, **kwargs):
    """Update node previous_status when node status changes."""
    if (instance.__previous_status != instance.status and
            instance.__previous_status not in (
                NODE_STATUS.RESCUE_MODE,
                NODE_STATUS.ENTERING_RESCUE_MODE,
                NODE_STATUS.FAILED_ENTERING_RESCUE_MODE,
                NODE_STATUS.EXITING_RESCUE_MODE,
                NODE_STATUS.FAILED_EXITING_RESCUE_MODE)):
        instance.previous_status = instance.__previous_status


for klass in NODE_CLASSES:
    signals.watch(
        pre_save, pre_save_update_status, sender=klass)


def clear_nodekey_when_owner_changes(node, old_values, deleted=False):
    """Erase related `NodeKey` when node ownership changes."""
    assert not deleted, (
        "clear_nodekey_when_owner_changes is not prepared "
        "to deal with deletion of nodes.")

    owner_id_old = old_values[0]
    owner_id_new = node.owner_id

    if owner_id_new != owner_id_old:
        NodeKey.objects.clear_token_for_node(node)

for klass in NODE_CLASSES:
    signals.watch_fields(
        clear_nodekey_when_owner_changes,
        klass, ['owner_id'], delete=False)


def create_services_on_node_type_change(node, old_values, deleted=False):
    """Create services when node_type changes."""
    old_node_type = old_values[0]
    new_node_type = node.node_type
    if new_node_type != old_node_type:
        Service.objects.create_services_for(node)


def create_services_on_create(sender, instance, created, **kwargs):
    """Create services when node created."""
    if created:
        Service.objects.create_services_for(instance)

for klass in NODE_CLASSES:
    signals.watch_fields(
        create_services_on_node_type_change,
        klass, ['node_type'], delete=False)
    signals.watch(
        post_save, create_services_on_create,
        sender=klass)


def decompose_machine_on_delete(sender, instance, **kwargs):
    """Decompose a machine if is part of a pod.

    This will block the deletion of the machine if the machine cannot
    be decomposed in the pod.
    """
    bmc = instance.bmc
    if (instance.node_type == NODE_TYPE.MACHINE and
            bmc is not None and
            bmc.bmc_type == BMC_TYPE.POD and
            Capabilities.COMPOSABLE in bmc.capabilities):
        pod = bmc.as_pod()

        @asynchronous
        def wrap_decompose_machine(
                client_idents, pod_type, parameters, pod_id, name):
            """Wrapper to get the client."""
            d = getClientFromIdentifiers(client_idents)
            d.addCallback(
                decompose_machine, pod_type, parameters,
                pod_id=pod_id, name=name)
            return d

        # Call the decompose in the reactor. This is being called from
        # a thread that will block waiting on the result. This sucks because
        # it causes the thread to block, but it will not cause a deadlock
        # as the work is performed in the reactor and not in another thread.
        hints = wrap_decompose_machine(
            pod.get_client_identifiers(),
            pod.power_type,
            instance.power_parameters,
            pod_id=pod.id,
            name=pod.name).wait(30)
        pod.sync_hints(hints)

for klass in NODE_CLASSES:
    signals.watch(
        pre_delete, decompose_machine_on_delete,
        sender=klass)


# Enable all signals by default.
signals.enable()
