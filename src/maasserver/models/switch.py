# Copyright 2017 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Switch objects."""


from django.db.models import CASCADE, CharField, Manager, OneToOneField

from maasserver import DefaultMeta
from maasserver.fields import JSONObjectField
from maasserver.models.cleansave import CleanSave
from maasserver.models.node import Node
from maasserver.models.timestampedmodel import TimestampedModel
from provisioningserver.logger import get_maas_logger

maaslog = get_maas_logger("switch")


class Switch(CleanSave, TimestampedModel):
    """A `Switch` represents an networking switch `Node` in the network.

    :ivar node: `Node` this `Switch` represents switch metadata for.
    :ivar nos_driver: The NOS driver defines which Network Operating System
        this switch uses.
    :ivar nos_parameters: Some JSON containing arbitrary parameters this
        Switch's NOS requires to function.
    :ivar objects: the switch manager class.
    """

    class Meta(DefaultMeta):
        verbose_name = "Switch"
        verbose_name_plural = "Switches"

    objects = Manager()

    node = OneToOneField(
        Node, null=False, blank=False, on_delete=CASCADE, primary_key=True
    )

    # The possible choices for this field depend on the NOS drivers advertised
    # by the rack controllers.  This needs to be populated on the fly, in
    # forms.py, each time the form to edit a node is instantiated.
    nos_driver = CharField(max_length=64, null=False, blank=True, default="")

    # JSON-encoded set of parameters for the NOS driver, limited to 32kiB when
    # encoded as JSON.
    nos_parameters = JSONObjectField(
        max_length=(2 ** 15), blank=True, default=""
    )

    def __str__(self):
        return "%s (%s)" % (self.__class__.__name__, self.node.hostname)

    def delete(self):
        """Delete this switch."""
        maaslog.info("%s: Deleting switch", self)
        super().delete()
