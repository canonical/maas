# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Respond to IP range changes."""

__all__ = [
    "signals",
]

from django.db.models.signals import (
    post_delete,
    post_save,
)
from maasserver.models import IPRange
from maasserver.utils.signals import SignalsManager


signals = SignalsManager()


def post_save_check_range_utilization(sender, instance, created, **kwargs):
    if instance.subnet is None:
        # Can't find a subnet to complain about. We're done here.
        return
    instance.subnet.update_allocation_notification()


def post_delete_check_range_utilization(sender, instance, **kwargs):
    if instance.subnet is None:
        # Can't find a subnet to complain about. We're done here.
        return
    instance.subnet.update_allocation_notification()


signals.watch(
    post_save, post_save_check_range_utilization, sender=IPRange)
signals.watch(
    post_delete, post_delete_check_range_utilization, sender=IPRange)


# Enable all signals by default.
signals.enable()
