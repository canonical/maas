# Copyright 2017 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).


from collections import Counter
from datetime import datetime
from typing import NamedTuple, Optional

from django.db.models import (
    CASCADE,
    CharField,
    Count,
    DateTimeField,
    Manager,
    Min,
    OneToOneField,
)

from maasserver import DefaultMeta
from maasserver.models.cleansave import CleanSave
from maasserver.models.node import Node
from maasserver.models.notification import Notification
from maasserver.models.timestampedmodel import TimestampedModel
from provisioningserver.enum import (
    CONTROLLER_INSTALL_TYPE,
    CONTROLLER_INSTALL_TYPE_CHOICES,
)
from provisioningserver.utils.version import MAASVersion


class ControllerInfoManager(Manager):
    def set_version(self, controller, version):
        self.update_or_create(defaults={"version": version}, node=controller)

    def set_versions_info(self, controller, versions):
        details = {
            "install_type": versions.install_type,
            "version": versions.current.version,
            # initialize other fields as null in case the controller is
            # upgraded from one install type to another
            "update_version": "",
            "update_origin": "",
            "snap_cohort": "",
            "snap_revision": "",
            "snap_update_revision": "",
            "update_first_reported": None,
        }
        if versions.install_type == CONTROLLER_INSTALL_TYPE.SNAP:
            details.update(
                {
                    "snap_revision": versions.current.revision,
                    "snap_cohort": versions.cohort,
                    "update_origin": str(versions.channel)
                    if versions.channel
                    else "",
                }
            )
        elif versions.install_type == CONTROLLER_INSTALL_TYPE.DEB:
            details["update_origin"] = versions.current.origin

        if versions.update:
            details.update(
                {
                    "update_version": versions.update.version,
                    "update_first_reported": datetime.now(),
                }
            )
            if versions.install_type == CONTROLLER_INSTALL_TYPE.DEB:
                # override the update origin as it might be different from the
                # installed one
                details["update_origin"] = versions.update.origin
            elif versions.install_type == CONTROLLER_INSTALL_TYPE.SNAP:
                details["snap_update_revision"] = versions.update.revision

        info, created = self.get_or_create(defaults=details, node=controller)
        if created:
            return

        if versions.update:
            if (
                versions.update.version == info.update_version
                and versions.install_type == info.install_type
            ):
                # if the version is the same but the install type has changed,
                # still update the first reported time
                del details["update_first_reported"]

        for key, value in details.items():
            setattr(info, key, value)
        info.save()


class ControllerInfo(CleanSave, TimestampedModel):
    """Metadata about a node that is a controller."""

    class Meta(DefaultMeta):
        verbose_name = "ControllerInfo"

    objects = ControllerInfoManager()

    node = OneToOneField(
        Node, null=False, blank=False, on_delete=CASCADE, primary_key=True
    )

    version = CharField(max_length=255, blank=True, default="")
    update_version = CharField(max_length=255, blank=True, default="")
    # the snap channel or deb repo for the update
    update_origin = CharField(max_length=255, blank=True, default="")
    update_first_reported = DateTimeField(blank=True, null=True)
    install_type = CharField(
        max_length=255,
        blank=True,
        choices=CONTROLLER_INSTALL_TYPE_CHOICES,
        default=CONTROLLER_INSTALL_TYPE.UNKNOWN,
    )
    snap_cohort = CharField(max_length=255, blank=True, default="")
    snap_revision = CharField(max_length=255, blank=True, default="")
    snap_update_revision = CharField(max_length=255, blank=True, default="")

    def __str__(self):
        return "%s (%s)" % (self.__class__.__name__, self.node.hostname)


def get_maas_version() -> Optional[MAASVersion]:
    """Return the version for the deployment.

    The returned version is the short version (up to the qualifier, if any)
    used by the most controllers.

    """
    version_data = (
        ControllerInfo.objects.exclude(version="")
        .values_list("version")
        .annotate(count=Count("node_id"))
    )
    versions = Counter()
    for version, count in version_data:
        versions[MAASVersion.from_string(version).main_version] += count
    # sort versions by the highest count first, and highest version in case of
    # equal count
    versions = sorted(
        ((count, version) for version, count in versions.items()), reverse=True
    )
    if not versions:
        return None
    return versions[0][1]


class TargetVersion(NamedTuple):
    """The target version for the MAAS deployment."""

    version: MAASVersion
    first_reported: Optional[datetime] = None


def get_target_version() -> Optional[TargetVersion]:
    """Get the target version for the deployment.

    If no updates are available, None is returned.
    """
    versions = (
        ControllerInfo.objects.exclude(update_version="")
        .values_list("update_version")
        .annotate(update_reported=Min("update_first_reported"))
    )
    versions = sorted(
        (
            (MAASVersion.from_string(version), first_reported)
            for version, first_reported in versions
        ),
        reverse=True,
    )
    if not versions:
        return None
    return TargetVersion(*versions[0])


UPGRADE_ISSUE_NOTIFICATION_IDENT = "upgrade_version_issue"
UPGRADE_STATUS_NOTIFICATION_IDENT = "upgrade_status"


def update_version_notifications():
    _process_udpate_issues_notification()
    _process_update_status_notification()


def _process_udpate_issues_notification():
    info = ControllerInfo.objects
    multiple_install_types = info.values("install_type").distinct().count() > 1
    multiple_origins = info.values("update_origin").distinct().count() > 1
    multiple_cohorts = info.values("snap_cohort").distinct().count() > 1
    multiple_versions = info.values("version").distinct().count() > 1
    multiple_upgrade_versions = (
        info.exclude(update_version="")
        .values("update_version")
        .distinct()
        .count()
        > 1
    )

    def set_warning(reason, message):
        defaults = {
            "category": "warning",
            "admins": True,
            "message": f"{message}. <a href='/MAAS/l/controllers'>Review controllers.</a>",
            "context": {"reason": reason},
        }
        notification, created = Notification.objects.get_or_create(
            ident=UPGRADE_ISSUE_NOTIFICATION_IDENT,
            defaults=defaults,
        )
        if not created and notification.context["reason"] != reason:
            # create a new notification so that it shows even if users have
            # dismissed the previous one
            notification.delete()
            Notification.objects.create(
                ident=UPGRADE_ISSUE_NOTIFICATION_IDENT, **defaults
            )

    if any((multiple_install_types, multiple_origins, multiple_cohorts)):
        set_warning(
            "install_source", "Controllers have different installation sources"
        )
    elif multiple_upgrade_versions:
        set_warning(
            "upgrade_versions", "Controllers report different upgrade versions"
        )
    elif multiple_versions:
        set_warning("versions", "Controllers have different versions")
    else:
        Notification.objects.filter(
            ident=UPGRADE_ISSUE_NOTIFICATION_IDENT
        ).delete()


def _process_update_status_notification():
    def set_update_notification(version, completed):
        context = {"version": str(version)}
        if completed:
            message = "MAAS has been updated to version {version}."
            context["status"] = "completed"
        else:
            message = (
                "MAAS {version} is available, controllers will upgrade soon."
            )
            context["status"] = "inprogress"

        defaults = {
            "category": "success" if completed else "info",
            "admins": True,
            "message": message,
            "context": context,
        }
        return Notification.objects.get_or_create(
            ident=UPGRADE_STATUS_NOTIFICATION_IDENT,
            defaults=defaults,
        )

    target_version = get_target_version()
    state_notification = Notification.objects.filter(
        ident=UPGRADE_STATUS_NOTIFICATION_IDENT
    ).first()
    if target_version:
        # an update is available
        update_version = target_version.version.main_version
        if state_notification:
            notification_version = MAASVersion.from_string(
                state_notification.context["version"]
            )
            if notification_version < update_version:
                # replace old notification with the new one
                state_notification.delete()
        set_update_notification(update_version, completed=False)
    elif state_notification:
        # no update but there's a previous notification
        current_version = get_maas_version().main_version
        notification_version = MAASVersion.from_string(
            state_notification.context["version"]
        )
        if (
            state_notification.context["status"] == "completed"
            and notification_version == current_version
        ):
            return
        state_notification.delete()
        set_update_notification(current_version, completed=True)
