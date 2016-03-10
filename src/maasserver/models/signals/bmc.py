# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Respond to BMC changes."""

__all__ = [
    "signals",
]

from django.db.models.signals import (
    post_delete,
    pre_delete,
)
from maasserver.models import BMC
from maasserver.utils.signals import SignalsManager


signals = SignalsManager()


def pre_delete_bmc_clean_orphaned_ip(sender, instance, **kwargs):
    """Stash the soon-to-be-deleted BMC's ip_address for use in post_delete."""
    instance.__previous_ip_address = instance.ip_address

signals.watch(
    pre_delete, pre_delete_bmc_clean_orphaned_ip, sender=BMC)


def post_delete_bmc_clean_orphaned_ip(sender, instance, **kwargs):
    """Removes the just-deleted BMC's ip_address if nobody else is using it.

    The potentially orphaned ip_address was stashed in the instance by the
    pre-delete signal handler.
    """
    if instance.__previous_ip_address is None:
        return
    if instance.__previous_ip_address.get_node() is not None:
        return
    if instance.__previous_ip_address.bmc_set.count() > 0:
        return
    # Delete the orphaned interface.
    instance.ip_address.delete()

signals.watch(
    post_delete, post_delete_bmc_clean_orphaned_ip, sender=BMC)

# Enable all signals by default.
signals.enable()
