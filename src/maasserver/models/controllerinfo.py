# Copyright 2017 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""ControllerInfo objects."""


from collections import namedtuple
import dataclasses

from django.db.models import CASCADE, CharField, Manager, OneToOneField

from maasserver import DefaultMeta
from maasserver.enum import NODE_TYPE
from maasserver.fields import JSONObjectField
from maasserver.models.cleansave import CleanSave
from maasserver.models.node import Node
from maasserver.models.timestampedmodel import TimestampedModel
from provisioningserver.logger import get_maas_logger
from provisioningserver.utils.version import get_version_tuple

maaslog = get_maas_logger("controllerinfo")


_ControllerVersionInfo = namedtuple(
    "ControllerVersionInfo",
    ("hostname", "system_id", "version", "maasversion"),
)


class ControllerVersionInfo(_ControllerVersionInfo):
    def difference(self, other):
        v1 = self.maasversion
        v2 = other.maasversion
        # No difference in the numeric versions
        if v1 == v2:
            return None, None
        # Indexes 0 through 5 will indicate the major, minor, patch, and
        # qualifier (such as alpha or beta qualifier), which is enough to know
        # we should display the full string instead of the short version.
        # (Since we already know they're not identical)
        elif dataclasses.astuple(v1)[0:5] == dataclasses.astuple(v2)[0:5]:
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
        if len(self.maasversion.extended_info) > 0:
            pretty_version = "%s (%s)" % (
                pretty_version,
                self.maasversion.extended_info,
            )
        return pretty_version


class ControllerInfoManager(Manager):
    def set_version(self, controller, version):
        self.update_or_create(defaults=dict(version=version), node=controller)

    def set_interface_update_info(self, controller, interfaces, hints):
        self.update_or_create(
            defaults=dict(interfaces=interfaces, interface_update_hints=hints),
            node=controller,
        )

    def get_controller_version_info(self):
        versions = list(
            self.select_related("node")
            .filter(
                node__node_type__in=(
                    NODE_TYPE.RACK_CONTROLLER,
                    NODE_TYPE.REGION_CONTROLLER,
                    NODE_TYPE.REGION_AND_RACK_CONTROLLER,
                ),
                version__isnull=False,
            )
            .values_list("node__hostname", "node__system_id", "version")
        )
        for i in range(len(versions)):
            version_info = list(versions[i])
            version_info.append(get_version_tuple(version_info[-1]))
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
    """A `ControllerInfo` represents metadata about nodes that are Controllers.

    :ivar node: `Node` this `ControllerInfo` represents metadata for.
    :ivar version: The last known version of the controller.
    :ivar interfaces: Interfaces JSON last sent by the controller.
    :ivar interface_udpate_hints: Topology hints last sent by the controller
        during a call to update_interfaces().
    """

    class Meta(DefaultMeta):
        verbose_name = "ControllerInfo"

    objects = ControllerInfoManager()

    node = OneToOneField(
        Node, null=False, blank=False, on_delete=CASCADE, primary_key=True
    )

    version = CharField(max_length=255, null=True, blank=True)

    interfaces = JSONObjectField(max_length=(2 ** 15), blank=True, default="")

    interface_update_hints = JSONObjectField(
        max_length=(2 ** 15), blank=True, default=""
    )

    def __str__(self):
        return "%s (%s)" % (self.__class__.__name__, self.node.hostname)
