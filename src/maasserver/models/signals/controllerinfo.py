# Copyright 2017 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Respond to ControllerInfo changes."""

from django.db.models.signals import post_delete, post_save

from maasserver.models import ControllerInfo, RackController, RegionController
from maasserver.models.controllerinfo import update_version_notifications
from maasserver.utils.signals import SignalsManager
from provisioningserver.logger import LegacyLogger

log = LegacyLogger()
signals = SignalsManager()


def post_save__update_version_notifications(
    sender, instance, created, **kwargs
):
    update_version_notifications()


def post_delete__update_version_notifications(sender, instance, **kwargs):
    update_version_notifications()


signals.watch(
    post_save, post_save__update_version_notifications, sender=ControllerInfo
)
signals.watch(
    post_delete,
    post_delete__update_version_notifications,
    sender=ControllerInfo,
)

# For some reason (maube due to the cascading delete behavior), we need to
# place signals not only on ControllerInfo, but also RegionController and
# RackController.
signals.watch(
    post_delete,
    post_delete__update_version_notifications,
    sender=RegionController,
)
signals.watch(
    post_delete,
    post_delete__update_version_notifications,
    sender=RackController,
)


# Enable all signals by default.
signals.enable()
