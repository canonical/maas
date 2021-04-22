# Copyright 2017 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).


from datetime import datetime
from typing import NamedTuple, Optional

from django.db.models import (
    CASCADE,
    CharField,
    DateTimeField,
    Manager,
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


class TargetVersion(NamedTuple):
    """The target version for the MAAS deployment."""

    version: MAASVersion
    first_reported: Optional[datetime] = None


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

    def get_target_version(self) -> TargetVersion:
        """Get the target version for the deployment."""
        highest_version, highest_update, update_first_reported = (
            None,
            None,
            None,
        )
        versions = self.exclude(version="").values_list(
            "version", "update_version", "update_first_reported"
        )
        for version, update, first_reported in versions:
            version = MAASVersion.from_string(version)
            highest_version = (
                max((highest_version, version)) if highest_version else version
            )

            if not update:
                continue

            update = MAASVersion.from_string(update)
            if not highest_update:
                highest_update = update
                update_first_reported = first_reported
            elif update < highest_update:
                continue
            elif update > highest_update:
                highest_update = update
                update_first_reported = first_reported
            else:  # same version
                update_first_reported = min(
                    (update_first_reported, first_reported)
                )

        if highest_update and highest_update > highest_version:
            return TargetVersion(highest_update, update_first_reported)
        return TargetVersion(highest_version)


UPGRADE_ISSUE_NOTIFICATION_IDENT = "upgrade_version_issue"


def update_version_notifications():
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
            "message": f"{message}. <a href='l/controllers'>Review controllers.</a>",
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
