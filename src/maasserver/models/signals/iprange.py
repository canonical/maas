# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Respond to IP range changes."""

from django.core.exceptions import ObjectDoesNotExist
from django.db.models.signals import post_delete, post_save

from maasserver.models import IPRange
from maasserver.utils.signals import SignalsManager

signals = SignalsManager()


def post_save_check_range_utilization(sender, instance, created, **kwargs):
    # Be careful when checking for the subnet. In rare cases, such as a
    # cascading delete, Django can sometimes pass stale model objects into
    # signal handlers, which will raise unexpected DoesNotExist exceptions,
    # and/or otherwise invalidate foreign key fields.
    # See bug #1702527 for more details.
    try:
        if instance.subnet is None:
            return
    except ObjectDoesNotExist:
        return
    instance.subnet.update_allocation_notification()


def post_delete_check_range_utilization(sender, instance, **kwargs):
    # Be careful when checking for the subnet. In rare cases, such as a
    # cascading delete, Django can sometimes pass stale model objects into
    # signal handlers, which will raise unexpected DoesNotExist exceptions,
    # and/or otherwise invalidate foreign key fields.
    # See bug #1702527 for more details.
    try:
        if instance.subnet is None:
            return
    except ObjectDoesNotExist:
        return
    instance.subnet.update_allocation_notification()


signals.watch(post_save, post_save_check_range_utilization, sender=IPRange)
signals.watch(post_delete, post_delete_check_range_utilization, sender=IPRange)


# Enable all signals by default.
signals.enable()
