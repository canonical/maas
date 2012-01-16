import datetime
from django.db import models
from django.contrib import admin

NODE_STATUS_CHOICES = (
    (u'NEW', u'New'),
    (u'READY', u'Ready to Commission'),
    (u'DEPLOYED', u'Deployed'),
    (u'COMM', u'Commissioned'),
    (u'DECOMM', u'Decommissioned'),
)


class Node(models.Model):
    name = models.CharField(max_length=30)
    status = models.CharField(max_length=10, choices=NODE_STATUS_CHOICES)
    created = models.DateField(editable=False)
    updated = models.DateTimeField(editable=False)

    def save(self):
        if not self.id:
            self.created = datetime.date.today()
        self.updated = datetime.datetime.today()
        super(Node, self).save()


admin.site.register(Node)
