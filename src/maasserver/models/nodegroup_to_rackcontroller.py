# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""
Store some of the old NodeGroup data so we can migrate it when a rack
controller is registered.
"""
from django.db.models import (
    CharField,
    ForeignKey,
    Model,
)
from maasserver.models.cleansave import CleanSave


class NodeGroupToRackController(CleanSave, Model):

    # The uuid of the nodegroup from < 2.0
    uuid = CharField(max_length=36, null=False, blank=False, editable=True)

    # The subnet that the nodegroup is connected to. There can be multiple
    # rows for multiple subnets on a signal nodegroup
    subnet = ForeignKey('Subnet', null=False, blank=False, editable=True)
