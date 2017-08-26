# Copyright 2017 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""ControllerInfo objects."""

__all__ = [
    "ControllerInfo",
    ]

from django.db.models import (
    CASCADE,
    CharField,
    Manager,
    OneToOneField,
)
from maasserver import DefaultMeta
from maasserver.fields import JSONObjectField
from maasserver.models.cleansave import CleanSave
from maasserver.models.node import Node
from maasserver.models.timestampedmodel import TimestampedModel
from provisioningserver.logger import get_maas_logger


maaslog = get_maas_logger("controllerinfo")


class ControllerInfoManager(Manager):

    def set_version(self, controller, version):
        self.update_or_create(defaults=dict(version=version), node=controller)

    def set_interface_update_info(self, controller, interfaces, hints):
        self.update_or_create(
            defaults=dict(interfaces=interfaces, interface_update_hints=hints),
            node=controller)


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
        Node, null=False, blank=False, on_delete=CASCADE, primary_key=True)

    version = CharField(max_length=255, null=True, blank=True)

    interfaces = JSONObjectField(max_length=(2 ** 15), blank=True, default='')

    interface_update_hints = JSONObjectField(
        max_length=(2 ** 15), blank=True, default='')

    def __str__(self):
        return "%s (%s)" % (self.__class__.__name__, self.node.hostname)
