# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""MaaS model objects."""

from __future__ import (
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = [
    "generate_node_system_id",
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
from django.core.files.base import ContentFile
from django.db import models
from django.db.models.signals import post_save
from django.shortcuts import get_object_or_404
from maasserver.exceptions import PermissionDenied
from maasserver.macaddress import MACAddressField
from piston.models import (
    Consumer,
    Token,
    )


class CommonInfo(models.Model):
    """A base model which records the creation date and the last modification
    date.

    :ivar created: The creation date.
    :ivar updated: The last modification date.

    """
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
    """The vocabulary of a `Node`'s possible statuses."""
# TODO: document this when it's stabilized.
    #:
    DEFAULT_STATUS = 0
    #:
    NEW = 0
    #:
    READY = 1
    #:
    DEPLOYED = 2
    #:
    COMMISSIONED = 3
    #:
    DECOMMISSIONED = 4


NODE_STATUS_CHOICES = (
    (NODE_STATUS.NEW, u'New'),
    (NODE_STATUS.READY, u'Ready to Commission'),
    (NODE_STATUS.DEPLOYED, u'Deployed'),
    (NODE_STATUS.COMMISSIONED, u'Commissioned'),
    (NODE_STATUS.DECOMMISSIONED, u'Decommissioned'),
)


NODE_STATUS_CHOICES_DICT = dict(NODE_STATUS_CHOICES)


class NODE_AFTER_COMMISSIONING_ACTION:
    """The vocabulary of a `Node`'s possible value for its field
    after_commissioning_action.

    """
# TODO: document this when it's stabilized.
    #:
    DEFAULT = 0
    #:
    QUEUE = 0
    #:
    CHECK = 1
    #:
    DEPLOY_12_04 = 2
    #:
    DEPLOY_11_10 = 3
    #:
    DEPLOY_11_04 = 4
    #:
    DEPLOY_10_10 = 5


NODE_AFTER_COMMISSIONING_ACTION_CHOICES = (
    (NODE_AFTER_COMMISSIONING_ACTION.QUEUE,
        "Queue for dynamic allocation to services"),
    (NODE_AFTER_COMMISSIONING_ACTION.CHECK,
        "Check compatibility and hold for future decision"),
    (NODE_AFTER_COMMISSIONING_ACTION.DEPLOY_12_04,
        "Deploy with Ubuntu 12.04 LTS"),
    (NODE_AFTER_COMMISSIONING_ACTION.DEPLOY_11_10,
        "Deploy with Ubuntu 11.10"),
    (NODE_AFTER_COMMISSIONING_ACTION.DEPLOY_11_04,
        "Deploy with Ubuntu 11.04"),
    (NODE_AFTER_COMMISSIONING_ACTION.DEPLOY_10_10,
        "Deploy with Ubuntu 10.10"),
)


NODE_AFTER_COMMISSIONING_ACTION_CHOICES_DICT = dict(
    NODE_AFTER_COMMISSIONING_ACTION_CHOICES)


class NodeManager(models.Manager):
    """A utility to manage the collection of Nodes."""

    def get_visible_nodes(self, user, ids=None):
        """Fetch all the Nodes visible by a User_.

        :param user: The user that should be used in the permission check.
        :type user: User_
        :param ids: If given, limit result to nodes with these system_ids.
        :type ids: Sequence.

        .. _User: https://
           docs.djangoproject.com/en/dev/topics/auth/
           #django.contrib.auth.models.User

        """
        if user.is_superuser:
            visible_nodes = self.all()
        else:
            visible_nodes = self.filter(
                models.Q(owner__isnull=True) | models.Q(owner=user))
        if ids is None:
            return visible_nodes
        else:
            return visible_nodes.filter(system_id__in=ids)

    def get_visible_node_or_404(self, system_id, user):
        """Fetch a `Node` by system_id.  Raise exceptions if no `Node` with
        this system_id exist or if the provided user cannot see this `Node`.

        :param name: The system_id.
        :type name: str
        :param user: The user that should be used in the permission check.
        :type user: django.contrib.auth.models.User
        :raises: django.http.Http404_,
            maasserver.exceptions.PermissionDenied_.

        .. _django.http.Http404: https://
           docs.djangoproject.com/en/dev/topics/http/views/
           #the-http404-exception
        """
        node = get_object_or_404(Node, system_id=system_id)
        if user.has_perm('access', node):
            return node
        else:
            raise PermissionDenied


class Node(CommonInfo):
    """A `Node` represents a physical machine used by the MaaS Server.

    :ivar system_id: The unique identifier for this `Node`.
        (e.g. 'node-41eba45e-4cfa-11e1-a052-00225f89f211').
    :ivar hostname: This `Node`'s hostname.
    :ivar status: This `Node`'s status. See the vocabulary
        :class:`NODE_STATUS`.
    :ivar owner: This `Node`'s owner if it's in use, None otherwise.
    :ivar after_commissioning_action: The action to perform after
        commissioning. See vocabulary
        :class:`NODE_AFTER_COMMISSIONING_ACTION`.
    :ivar objects: The :class:`NodeManager`.
    :ivar hostname: This `Node`'s hostname.

    """

    system_id = models.CharField(
        max_length=41, unique=True, default=generate_node_system_id,
        editable=False)

    hostname = models.CharField(max_length=255, default='', blank=True)

    status = models.IntegerField(
        max_length=10, choices=NODE_STATUS_CHOICES, editable=False,
        default=NODE_STATUS.DEFAULT_STATUS)

    owner = models.ForeignKey(
        User, default=None, blank=True, null=True, editable=False)

    after_commissioning_action = models.IntegerField(
        choices=NODE_AFTER_COMMISSIONING_ACTION_CHOICES,
        default=NODE_AFTER_COMMISSIONING_ACTION.DEFAULT)

    objects = NodeManager()

    def __unicode__(self):
        if self.hostname:
            return u"%s (%s)" % (self.system_id, self.hostname)
        else:
            return self.system_id

    def display_status(self):
        return NODE_STATUS_CHOICES_DICT[self.status]

    def add_mac_address(self, mac_address):
        """Add a new MAC Address to this `Node`.

        :param mac_address: The MAC Address to be added.
        :type mac_address: str
        :raises: django.core.exceptions.ValidationError_

        .. _django.core.exceptions.ValidationError: https://
           docs.djangoproject.com/en/dev/ref/exceptions/
           #django.core.exceptions.ValidationError
        """

        mac = MACAddress(mac_address=mac_address, node=self)
        mac.full_clean()
        mac.save()
        return mac

    def remove_mac_address(self, mac_address):
        """Remove a MAC Address from this `Node`.

        :param mac_address: The MAC Address to be removed.
        :type mac_address: str

        """
        mac = MACAddress.objects.get(mac_address=mac_address, node=self)
        if mac:
            mac.delete()


mac_re = re.compile(r'^([0-9a-fA-F]{2}:){5}[0-9a-fA-F]{2}$')


class MACAddress(CommonInfo):
    """A `MACAddress` represents a `MAC Address
    <http://en.wikipedia.org/wiki/MAC_address>`_ attached to a :class:`Node`.

    :ivar mac_address: The MAC Address.
    :ivar node: The `Node` related to this `MACAddress`.

    """
    mac_address = MACAddressField()
    node = models.ForeignKey(Node, editable=False)

    class Meta:
        verbose_name_plural = "MAC addresses"

    def __unicode__(self):
        return self.mac_address


GENERIC_CONSUMER = 'Maas consumer'


class UserProfile(models.Model):
    """A User profile to store Maas specific methods and fields.

    :ivar user: The related User_.

    .. _UserProfile: https://docs.djangoproject.com/
       en/dev/topics/auth/
       #storing-additional-information-about-users

    """

    user = models.OneToOneField(User)

    def reset_authorisation_token(self):
        """Create (if necessary) and regenerate the keys for the Consumer and
        the related Token of the OAuth authorisation.

        :return: A tuple containing the Consumer and the Token that were reset.
        :rtype: tuple

        """
        consumer, _ = Consumer.objects.get_or_create(
            user=self.user, name=GENERIC_CONSUMER,
            defaults={'status': 'accepted'})
        consumer.generate_random_codes()
        # This is a 'generic' consumer aimed to service many clients, hence
        # we don't authenticate the consumer with key/secret key.
        consumer.secret = ''
        consumer.save()
        token, _ = Token.objects.get_or_create(
            user=self.user, token_type=Token.ACCESS, consumer=consumer,
            defaults={'is_approved': True})
        token.generate_random_codes()
        return consumer, token

    def get_authorisation_consumer(self):
        """Returns the OAuth Consumer attached to the related User_.

        :return: The attached Consumer.
        :rtype: piston.models.Consumer

        """
        return Consumer.objects.get(user=self.user, name=GENERIC_CONSUMER)

    def get_authorisation_token(self):
        """Returns the OAuth authorisation token attached to the related User_.

        :return: The attached Token.
        :rtype: piston.models.Token

        """
        consumer = self.get_authorisation_consumer()
        token = Token.objects.get(
            user=self.user, token_type=Token.ACCESS, consumer=consumer)
        return token


# When a user is created: create the related profile and the default
# consumer/token.
def create_user(sender, instance, created, **kwargs):
    if created:
        # Create related UserProfile.
        profile = UserProfile.objects.create(user=instance)

        # Create initial authorisation token.
        profile.reset_authorisation_token()

# Connect the 'create_user' method to the post save signal of User.
post_save.connect(create_user, sender=User)


class FileStorage(models.Model):
    """A simple file storage keyed on file name.

    :ivar filename: A unique file name to use for the data being stored.
    :ivar data: The file's actual data.
    """

    filename = models.CharField(max_length=255, unique=True, editable=False)
    data = models.FileField(upload_to="storage")

    def __unicode__(self):
        return self.filename

    def save_file(self, filename, file_object):
        """Save the file to the filesystem and persist to the database.

        The file will end up in MEDIA_ROOT/storage/
        """
        self.filename = filename
        # This probably ought to read in chunks but large files are
        # not expected.  Also note that uploading a file with the same
        # name as an existing one will cause that file to be written
        # with a new generated name, and the old one remains where it
        # is.  See https://code.djangoproject.com/ticket/6157 - the
        # Django devs consider deleting things dangerous ... ha.
        # HOWEVER - this operation would need to be atomic anyway so
        # it's safest left how it is for now (reads can overlap with
        # writes from Juju).
        content = ContentFile(file_object.read())
        self.data.save(filename, content)


# Register the models in the admin site.
admin.site.register(Consumer)
admin.site.register(FileStorage)
admin.site.register(MACAddress)
admin.site.register(Node)


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
