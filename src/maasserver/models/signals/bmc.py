# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Respond to BMC changes."""

from django.db.models.signals import post_delete, post_save, pre_delete

from maasserver.enum import BMC_TYPE
from maasserver.models import BMC, Pod, PodHints
from maasserver.utils.signals import SignalsManager

BMC_CLASSES = [BMC, Pod]

signals = SignalsManager()


def pre_delete_bmc_clean_orphaned_ip(sender, instance, **kwargs):
    """Stash the soon-to-be-deleted BMC's ip_address for use in post_delete."""
    instance.__previous_ip_address = instance.ip_address


for klass in BMC_CLASSES:
    signals.watch(pre_delete, pre_delete_bmc_clean_orphaned_ip, sender=klass)


def post_delete_bmc_clean_orphaned_ip(sender, instance, **kwargs):
    """Removes the just-deleted BMC's ip_address if nobody else is using it.

    The potentially orphaned ip_address was stashed in the instance by the
    pre-delete signal handler.
    """
    if instance.__previous_ip_address is None:
        return
    if instance.__previous_ip_address.get_node() is not None:
        return
    if instance.__previous_ip_address.bmc_set.exists():
        return
    # Delete the orphaned interface.
    instance.__previous_ip_address.delete()


for klass in BMC_CLASSES:
    signals.watch(post_delete, post_delete_bmc_clean_orphaned_ip, sender=klass)


def create_pod_hints(sender, instance, created, **kwargs):
    """Create `PodHints` when `Pod` is created."""
    if instance.bmc_type == BMC_TYPE.POD:
        PodHints.objects.get_or_create(pod=instance)
    else:
        PodHints.objects.filter(pod__id=instance.id).delete()


for klass in BMC_CLASSES:
    signals.watch(post_save, create_pod_hints, sender=klass)

# Enable all signals by default.
signals.enable()
