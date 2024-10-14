# Copyright 2020 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Release Notifications for MAAS

Checks for new MAAS releases in the images.maas.io stream and creates
notifications for the user.
"""

from dataclasses import dataclass
from datetime import timedelta

from django.utils import timezone
from twisted.internet.defer import inlineCallbacks

from maasserver.models import Config, Notification
from maasserver.models.controllerinfo import get_maas_version
from maasserver.utils.orm import transactional
from maasserver.utils.threads import deferToDatabase
from provisioningserver.logger import get_maas_logger, LegacyLogger
from provisioningserver.utils.twisted import asynchronous
from provisioningserver.utils.version import MAASVersion

maaslog = get_maas_logger("release-notifications")
log = LegacyLogger()

RELEASE_NOTIFICATION_SERVICE_PERIOD = timedelta(hours=24)
RESURFACE_AFTER = timedelta(weeks=2)
RELEASE_NOTIFICATION_IDENT = "release_notification"


@dataclass
class ReleaseNotification:
    maas_version: str
    message: str
    # Product version number
    version: float


class NoReleasenotification(LookupError):
    pass


def notification_available(notification_version):
    current_version = get_maas_version()
    notification_version = MAASVersion.from_string(notification_version)
    log.debug(f"Current MAAS version: {current_version}")
    log.debug(f"Notification version: {notification_version}")
    return notification_version > current_version


@transactional
def ensure_notification_exists(message, resurface_after=RESURFACE_AFTER):
    notification, created = Notification.objects.get_or_create(
        ident=RELEASE_NOTIFICATION_IDENT,
        defaults={
            "message": message,
            "category": "info",
            "users": True,
            "admins": True,
        },
    )
    if created:
        # Since this is a new notification there is nothing else to do. It will
        # now be showen to all users
        return

    # Only the message will be updated in release notifications.
    if notification.message != message:
        notification.message = message
        notification.save()
        # If the notification is being updated, we want to resuface it for all
        # users by deleting their dismissals
        notification.notificationdismissal_set.all().delete()
        return

    notification.notificationdismissal_set.filter(
        updated__lt=timezone.now() - resurface_after
    ).delete()


class ReleaseNotifications:
    def __init__(self, release_notification):
        self.release_notification = ReleaseNotification(**release_notification)

    def maybe_check_release_notifications(self):
        def check_config():
            return Config.objects.get_config("release_notifications")

        d = deferToDatabase(transactional(check_config))
        d.addCallback(self.check_notifications)
        d.addErrback(log.err, "Failure checking release notifications.")
        return d

    def cleanup_notification(self):
        maaslog.debug("Cleaning up notifications")
        Notification.objects.filter(ident=RELEASE_NOTIFICATION_IDENT).delete()

    @asynchronous
    @inlineCallbacks
    def check_notifications(self, notifications_enabled):
        if not notifications_enabled:
            maaslog.debug("Release notifications are disabled")
            # Notifications are disabled, we can delete any that currently exist.
            yield deferToDatabase(transactional(self.cleanup_notification))
            return

        if not notification_available(self.release_notification.maas_version):
            maaslog.debug("No new release notifications available")
            return

        maaslog.debug("Notification to display")
        yield deferToDatabase(
            ensure_notification_exists, self.release_notification.message
        )
