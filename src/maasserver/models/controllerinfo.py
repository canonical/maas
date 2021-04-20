# Copyright 2017 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""ControllerInfo objects."""


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
from maasserver.enum import NODE_TYPE
from maasserver.models.cleansave import CleanSave
from maasserver.models.node import Node
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


class ControllerVersionInfo(NamedTuple):

    hostname: str
    system_id: str
    version: str
    maasversion: MAASVersion

    def difference(self, other):
        v1 = self.maasversion
        v2 = other.maasversion
        # No difference in the numeric versions
        if v1 == v2:
            return None, None
        elif v1.short_version == v2.short_version:
            # If versions match up to the qualifier version, show the full
            # strings
            return self.full_string, other.full_string
        else:
            # Only difference is the revision number, so just display the
            # full string.
            return (
                self.maasversion.short_version,
                other.maasversion.short_version,
            )

    @property
    def full_string(self):
        pretty_version = self.maasversion.short_version
        if self.maasversion.extended_info:
            pretty_version += f" ({self.maasversion.extended_info})"
        return pretty_version


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

    def get_controller_version_info(self):
        versions = list(
            self.select_related("node")
            .filter(
                node__node_type__in=(
                    NODE_TYPE.RACK_CONTROLLER,
                    NODE_TYPE.REGION_CONTROLLER,
                    NODE_TYPE.REGION_AND_RACK_CONTROLLER,
                ),
            )
            .exclude(version="")
            .values_list("node__hostname", "node__system_id", "version")
        )
        for i in range(len(versions)):
            version_info = list(versions[i])
            version_info.append(MAASVersion.from_string(version_info[-1]))
            versions[i] = ControllerVersionInfo(*version_info)
        return sorted(versions, key=lambda version: version[-1], reverse=True)


VERSION_NOTIFICATION_IDENT = "controller_out_of_date_"


def create_or_update_version_notification(system_id, message, context):
    # Circular imports.
    from maasserver.models import Notification

    ident = VERSION_NOTIFICATION_IDENT + system_id
    existing_notification = Notification.objects.filter(ident=ident).first()
    if existing_notification is not None:
        existing_notification.message = message
        existing_notification.context = context
        existing_notification.save()
    else:
        Notification.objects.create_warning_for_admins(
            message, context=context, ident=ident
        )


KNOWN_VERSION_MISMATCH_NOTIFICATION = (
    "Controller <a href='l/controller/{system_id}'>{hostname}</a> is "
    "running an older version of MAAS ({v1})."
)

UNKNOWN_VERSION_MISMATCH_NOTIFICATION = (
    "Controller <a href='l/controller/{system_id}'>{hostname}</a> "
    "is running an older version of MAAS (less than 2.3.0)."
)


def update_version_notifications():
    notifications = {}
    # Circular imports.
    from maasserver.models import Controller, Notification

    controller_system_ids = set(
        Controller.objects.all().values_list("system_id", flat=True)
    )
    controller_version_info = (
        ControllerInfo.objects.get_controller_version_info()
    )
    now_possibly_irrelevant_notifications = set(
        Notification.objects.filter(
            ident__startswith=VERSION_NOTIFICATION_IDENT
        ).values_list("ident", flat=True)
    )
    just_one_controller = len(controller_system_ids) == 1
    if len(controller_version_info) == 0 or just_one_controller:
        # No information means no notifications should be presented, and
        # any existing notifications should be removed.
        Notification.objects.filter(
            ident__in=now_possibly_irrelevant_notifications
        ).delete()
        return
    # The list is sorted with the first element being the controller
    # with the highest version. So we can use that to compare with
    # the remaining controllers.
    latest_controller_version_info = controller_version_info[0]
    latest_version = latest_controller_version_info.maasversion
    for controller in controller_version_info:
        if controller.maasversion < latest_version:
            v1, v2 = controller.difference(latest_controller_version_info)
            context = dict(
                message=KNOWN_VERSION_MISMATCH_NOTIFICATION,
                hostname=controller.hostname,
                v1=v1,
                v2=v2,
                system_id=controller.system_id,
            )
            notifications[controller.system_id] = context
            now_possibly_irrelevant_notifications.discard(
                VERSION_NOTIFICATION_IDENT + controller.system_id
            )
        else:
            # This will indicate that a notification isn't required, or
            # any existing notification should be deleted.
            notifications[controller.system_id] = None
            controller_system_ids.discard(controller.system_id)
    for system_id, context in notifications.items():
        ident = VERSION_NOTIFICATION_IDENT + system_id
        if context is None:
            Notification.objects.filter(ident=ident).delete()
            continue
        message = context.pop("message")
        create_or_update_version_notification(system_id, message, context)
        controller_system_ids.discard(system_id)
    # The remaining items in the controller_system_ids set will be
    # controllers old enough that we don't know their version.
    for system_id in controller_system_ids:
        controller = Controller.objects.filter(system_id=system_id).first()
        message = UNKNOWN_VERSION_MISMATCH_NOTIFICATION
        context = dict(
            hostname=controller.hostname,
            system_id=controller.system_id,
            latest_version=(
                latest_controller_version_info.maasversion.short_version
            ),
        )
        create_or_update_version_notification(system_id, message, context)
    # Delete any remaining notifications. These might be for controllers
    # that no longer exist. Any current notifications will have been
    # discarded from the set of existing notifications.
    Notification.objects.filter(
        ident__in=now_possibly_irrelevant_notifications
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
