import datetime
import re
from uuid import uuid1

from django.db import models
from django.contrib import admin
from django.core.validators import RegexValidator


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
    hostname = models.CharField(max_length=255)
    status = models.CharField(max_length=10, choices=NODE_STATUS_CHOICES)

    def __unicode__(self):
        return self.system_id


mac_re = re.compile(r'^([0-9a-fA-F]{2}:){5}[0-9a-fA-F]{2}$')


validate_mac_address = RegexValidator(
    regex = mac_re,
    message = u'Enter a valid MAC address (e.g. AA:BB:CC:DD:EE:FF).')


class MACAddress(CommonInfo):
    mac_address = models.CharField(
        max_length=17, validators=[validate_mac_address])
    node = models.ForeignKey(Node)

    def __unicode__(self):
        return self.mac_address


# Register the models in the admin site.
admin.site.register(Node)
admin.site.register(MACAddress)

