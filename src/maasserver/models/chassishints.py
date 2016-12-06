# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Model that holds hint information for a Chassis."""

__all__ = [
    'ChassisHints',
    ]


from django.db.models import (
    IntegerField,
    Model,
    OneToOneField,
)
from maasserver import DefaultMeta
from maasserver.models.cleansave import CleanSave
from maasserver.models.node import Node


class ChassisHints(CleanSave, Model):
    """Hint information for a chassis."""

    class Meta(DefaultMeta):
        """Needed for South to recognize this model."""

    chassis = OneToOneField(Node, related_name="chassis_hints")

    cores = IntegerField(default=0)

    memory = IntegerField(default=0)

    local_storage = IntegerField(default=0)
