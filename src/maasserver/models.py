# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Model."""

from __future__ import (
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = [
    "NODE_STATUS",
    "Node",
    "MACAddress",
    ]

import datetime
import re
from uuid import uuid1

from django.contrib import admin
from django.contrib.auth.backends import ModelBackend
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied
from django.db import models
from django.shortcuts import get_object_or_404
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


class NODE_STATUS:
    DEFAULT_STATUS = 0
    NEW = 0
    READY = 1
    DEPLOYED = 2
    COMMISSIONED = 3
    DECOMMISSIONED = 4


NODE_STATUS_CHOICES = (
    (NODE_STATUS.NEW, u'New'),
    (NODE_STATUS.READY, u'Ready to Commission'),
    (NODE_STATUS.DEPLOYED, u'Deployed'),
    (NODE_STATUS.COMMISSIONED, u'Commissioned'),
    (NODE_STATUS.DECOMMISSIONED, u'Decommissioned'),
)


NODE_STATUS_CHOICES_DICT = dict(NODE_STATUS_CHOICES)


class NodeManager(models.Manager):
    """A utility to manage collections of Nodes."""

    def get_visible_nodes(self, user):
        """Fetch all the `Nodes` visible by a User.  Available via
        `Node.objects`.

        :param user: The user that should be used in the permission check.
        :type user: django.contrib.auth.models.User

        """
        if user.is_superuser:
            return self.all()
        else:
            return self.filter(
                models.Q(owner__isnull=True) | models.Q(owner=user))

    def get_visible_node_or_404(self, system_id, user):
        """Fetch a `Node` by system_id.  Raise exceptions if no `Node` with
        this system_id exist or if the provided user cannot see this `Node`.

        :param name: The system_id.
        :type name: str
        :param user: The user that should be used in the permission check.
        :type user: django.contrib.auth.models.User
        :raises: django.http.Http404, django.core.exceptions.PermissionDenied

        """
        node = get_object_or_404(Node, system_id=system_id)
        if user.has_perm('access', node):
            return node
        else:
            raise PermissionDenied


class Node(CommonInfo):
    """A `Node` represents a physical machine used by the MaaS Server."""
    system_id = models.CharField(
        max_length=41, unique=True, editable=False,
        default=generate_node_system_id)
    hostname = models.CharField(max_length=255, default='', blank=True)
    status = models.IntegerField(
        max_length=10, choices=NODE_STATUS_CHOICES, editable=False,
        default=NODE_STATUS.DEFAULT_STATUS)
    owner = models.ForeignKey(
        User, default=None, blank=True, null=True, editable=False)

    objects = NodeManager()

    def __unicode__(self):
        if self.hostname:
            return u"%s (%s)" % (self.system_id, self.hostname)
        else:
            return self.system_id

    def display_status(self):
        return NODE_STATUS_CHOICES_DICT[self.status]

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
    """A `MACAddress` represents a `MAC Address
    <http://en.wikipedia.org/wiki/MAC_address>`_ attached to a `Node`.
    """
    mac_address = MACAddressField()
    node = models.ForeignKey(Node)

    class Meta:
        verbose_name_plural = "MAC addresses"

    def __unicode__(self):
        return self.mac_address


# Register the models in the admin site.
admin.site.register(Node)
admin.site.register(MACAddress)


class MaaSAuthorizationBackend(ModelBackend):

    supports_object_permissions = True

    def has_perm(self, user, perm, obj=None):
        # Only Nodes can be checked. We also don't support perm checking
        # when obj = None.
        if not isinstance(obj, Node):
            raise NotImplementedError(
                'Invalid permission check (invalid object type).')

        # Only the generic 'access' permission is supported.
        if perm != 'access':
            raise NotImplementedError(
                'Invalid permission check (invalid permission name).')

        return obj.owner in (None, user)
