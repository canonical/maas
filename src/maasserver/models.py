# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from __future__ import (
    print_function,
    unicode_literals,
    )

"""Model."""

__metaclass__ = type
__all__ = [
    "Node",
    "MACAddress",
    ]

import datetime
import re
from uuid import uuid1

from django.contrib import admin
from django.db import models
from maasserver.macaddress import MACAddressField


class CommonInfo(models.Model):
    created = models.DateField(editable=False)
    updated = models.DateTimeField(editable=False)

    class Meta:
        abstract = True

    def save(self):
        if not self.id:
            self.created = datetime.date.today()
        self.updated = datetime.datetime.today()
        super(CommonInfo, self).save()


def generate_node_system_id():
    return 'node-%s' % uuid1()


NODE_STATUS_CHOICES = (
    (u'NEW', u'New'),
    (u'READY', u'Ready to Commission'),
    (u'DEPLOYED', u'Deployed'),
    (u'COMM', u'Commissioned'),
    (u'DECOMM', u'Decommissioned'),
)


class Node(CommonInfo):
    system_id = models.CharField(
        max_length=41, unique=True, editable=False,
        default=generate_node_system_id)
    hostname = models.CharField(max_length=255, default='')
    status = models.CharField(max_length=10, choices=NODE_STATUS_CHOICES)

    def __unicode__(self):
        return self.system_id

    def add_mac_address(self, mac_address):
        mac = MACAddress(mac_address=mac_address, node=self)
        mac.full_clean()
        mac.save()
        return mac

    def remove_mac_address(self, mac_address):
        mac = MACAddress.objects.filter(mac_address=mac_address, node=self)
        mac.delete()


mac_re = re.compile(r'^([0-9a-fA-F]{2}:){5}[0-9a-fA-F]{2}$')


class MACAddress(CommonInfo):
    mac_address = MACAddressField()
    node = models.ForeignKey(Node)

    def __unicode__(self):
        return self.mac_address


# Register the models in the admin site.
admin.site.register(Node)
admin.site.register(MACAddress)
