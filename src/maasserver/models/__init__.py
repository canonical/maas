# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""MAAS model objects.

DO NOT add new models to this module.  Add them to the package as separate
modules, but import them here and add them to `__all__`.
"""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = [
    "create_auth_token",
    "generate_node_system_id",
    "get_auth_tokens",
    "get_db_state",
    "logger",
    "Config",
    "FileStorage",
    "NODE_TRANSITIONS",
    "Node",
    "MACAddress",
    "SSHKey",
    "UserProfile",
    ]

import binascii
from cgi import escape
from logging import getLogger
import os
import re
from string import whitespace
from uuid import uuid1

from django.conf import settings
from django.contrib import admin
from django.contrib.auth.backends import ModelBackend
from django.contrib.auth.models import User
from django.core.exceptions import (
    PermissionDenied,
    ValidationError,
    )
from django.db import connection
from django.db.models import (
    CharField,
    ForeignKey,
    IntegerField,
    Manager,
    Model,
    OneToOneField,
    Q,
    TextField,
    )
from django.db.models.signals import post_save
from django.shortcuts import get_object_or_404
from django.utils.safestring import mark_safe
from maasserver import DefaultMeta
from maasserver.fields import JSONObjectField
from maasserver.enum import (
    ARCHITECTURE,
    ARCHITECTURE_CHOICES,
    NODE_AFTER_COMMISSIONING_ACTION,
    NODE_AFTER_COMMISSIONING_ACTION_CHOICES,
    NODE_PERMISSION,
    NODE_STATUS,
    NODE_STATUS_CHOICES,
    NODE_STATUS_CHOICES_DICT,
    )
from maasserver.exceptions import (
    CannotDeleteUserException,
    NodeStateViolation,
    )
from maasserver.fields import MACAddressField
from maasserver.models.cleansave import CleanSave
from maasserver.models.config import Config
from maasserver.models.filestorage import FileStorage
from maasserver.models.timestampedmodel import TimestampedModel
from metadataserver import nodeinituser
from piston.models import (
    Consumer,
    Token,
    )
from provisioningserver.enum import (
    POWER_TYPE,
    POWER_TYPE_CHOICES,
    )
from provisioningserver.tasks import power_on
from twisted.conch.ssh.keys import (
    BadKeyError,
    Key,
    )

# Special users internal to MAAS.
SYSTEM_USERS = [
    # For nodes' access to the metadata API:
    nodeinituser.user_name,
    ]


logger = getLogger('maasserver')


def now():
    cursor = connection.cursor()
    cursor.execute("select now()")
    return cursor.fetchone()[0]


def generate_node_system_id():
    return 'node-%s' % uuid1()


# Information about valid node status transitions.
# The format is:
# {
#  old_status1: [
#      new_status11,
#      new_status12,
#      new_status13,
#      ],
# ...
# }
#
NODE_TRANSITIONS = {
    None: [
        NODE_STATUS.DECLARED,
        NODE_STATUS.MISSING,
        NODE_STATUS.RETIRED,
        ],
    NODE_STATUS.DECLARED: [
        NODE_STATUS.COMMISSIONING,
        NODE_STATUS.MISSING,
        NODE_STATUS.READY,
        NODE_STATUS.RETIRED,
        ],
    NODE_STATUS.COMMISSIONING: [
        NODE_STATUS.FAILED_TESTS,
        NODE_STATUS.READY,
        NODE_STATUS.RETIRED,
        NODE_STATUS.MISSING,
        ],
    NODE_STATUS.FAILED_TESTS: [
        NODE_STATUS.COMMISSIONING,
        NODE_STATUS.MISSING,
        NODE_STATUS.RETIRED,
        ],
    NODE_STATUS.READY: [
        NODE_STATUS.ALLOCATED,
        NODE_STATUS.RESERVED,
        NODE_STATUS.RETIRED,
        NODE_STATUS.MISSING,
        ],
    NODE_STATUS.RESERVED: [
        NODE_STATUS.READY,
        NODE_STATUS.ALLOCATED,
        NODE_STATUS.RETIRED,
        NODE_STATUS.MISSING,
        ],
    NODE_STATUS.ALLOCATED: [
        NODE_STATUS.READY,
        NODE_STATUS.RETIRED,
        NODE_STATUS.MISSING,
        ],
    NODE_STATUS.MISSING: [
        NODE_STATUS.DECLARED,
        NODE_STATUS.READY,
        NODE_STATUS.ALLOCATED,
        NODE_STATUS.COMMISSIONING,
        ],
    NODE_STATUS.RETIRED: [
        NODE_STATUS.DECLARED,
        NODE_STATUS.READY,
        NODE_STATUS.MISSING,
        ],
    }


def get_papi():
    """Return a provisioning server API proxy."""
    # Avoid circular imports.
    from maasserver.provisioning import get_provisioning_api_proxy
    return get_provisioning_api_proxy()


class NodeManager(Manager):
    """A utility to manage the collection of Nodes."""

    def filter_by_ids(self, query, ids=None):
        """Filter `query` result set by system_id values.

        :param query: A QuerySet of Nodes.
        :type query: django.db.models.query.QuerySet_
        :param ids: Optional set of ids to filter by.  If given, nodes whose
            system_ids are not in `ids` will be ignored.
        :type param_ids: Sequence
        :return: A filtered version of `query`.

        .. _django.db.models.query.QuerySet: https://docs.djangoproject.com/
           en/dev/ref/models/querysets/

        """
        if ids is None:
            return query
        else:
            return query.filter(system_id__in=ids)

    def get_nodes(self, user, perm, ids=None):
        """Fetch Nodes on which the User_ has the given permission.

        :param user: The user that should be used in the permission check.
        :type user: User_
        :param perm: The permission to check.
        :type perm: a permission string from NODE_PERMISSION
        :param ids: If given, limit result to nodes with these system_ids.
        :type ids: Sequence.

        .. _User: https://
           docs.djangoproject.com/en/dev/topics/auth/
           #django.contrib.auth.models.User

        """
        if user.is_superuser:
            nodes = self.all()
        else:
            if perm == NODE_PERMISSION.VIEW:
                nodes = self.filter(Q(owner__isnull=True) | Q(owner=user))
            elif perm == NODE_PERMISSION.EDIT:
                nodes = self.filter(owner=user)
            elif perm == NODE_PERMISSION.ADMIN:
                nodes = self.none()
            else:
                raise NotImplementedError(
                    "Invalid permission check (invalid permission name: %s)." %
                    perm)

        return self.filter_by_ids(nodes, ids)

    def get_allocated_visible_nodes(self, token, ids):
        """Fetch Nodes that were allocated to the User_/oauth token.

        :param user: The user whose nodes to fetch
        :type user: User_
        :param token: The OAuth token associated with the Nodes.
        :type token: piston.models.Token.
        :param ids: Optional set of IDs to filter by. If given, nodes whose
            system_ids are not in `ids` will be ignored.
        :type param_ids: Sequence

        .. _User: https://
           docs.djangoproject.com/en/dev/topics/auth/
           #django.contrib.auth.models.User
        """
        if ids is None:
            nodes = self.filter(token=token)
        else:
            nodes = self.filter(token=token, system_id__in=ids)
        return nodes

    def get_node_or_404(self, system_id, user, perm):
        """Fetch a `Node` by system_id.  Raise exceptions if no `Node` with
        this system_id exist or if the provided user has not the required
        permission on this `Node`.

        :param name: The system_id.
        :type name: str
        :param user: The user that should be used in the permission check.
        :type user: django.contrib.auth.models.User
        :param perm: The permission to assert that the user has on the node.
        :type perm: basestring
        :raises: django.http.Http404_,
            :class:`maasserver.exceptions.PermissionDenied`.

        .. _django.http.Http404: https://
           docs.djangoproject.com/en/dev/topics/http/views/
           #the-http404-exception
        """
        node = get_object_or_404(Node, system_id=system_id)
        if user.has_perm(perm, node):
            return node
        else:
            raise PermissionDenied()

    def get_available_node_for_acquisition(self, for_user, constraints=None):
        """Find a `Node` to be acquired by the given user.

        :param for_user: The user who is to acquire the node.
        :type for_user: :class:`django.contrib.auth.models.User`
        :param constraints: Optional selection constraints.  If given, only
            nodes matching these constraints are considered.
        :type constraints: :class:`dict`
        :return: A matching `Node`, or None if none are available.
        """
        if constraints is None:
            constraints = {}
        available_nodes = (
            self.get_nodes(for_user, NODE_PERMISSION.VIEW)
                .filter(status=NODE_STATUS.READY))

        if constraints.get('name'):
            available_nodes = available_nodes.filter(
                hostname=constraints['name'])

        available_nodes = list(available_nodes[:1])
        if len(available_nodes) == 0:
            return None
        else:
            return available_nodes[0]

    def stop_nodes(self, ids, by_user):
        """Request on given user's behalf that the given nodes be shut down.

        Shutdown is only requested for nodes that the user has ownership
        privileges for; any other nodes in the request are ignored.

        :param ids: The `system_id` values for nodes to be shut down.
        :type ids: Sequence
        :param by_user: Requesting user.
        :type by_user: User_
        :return: Those Nodes for which shutdown was actually requested.
        :rtype: list
        """
        nodes = self.get_nodes(by_user, NODE_PERMISSION.EDIT, ids=ids)
        get_papi().stop_nodes([node.system_id for node in nodes])
        return nodes

    def start_nodes(self, ids, by_user, user_data=None):
        """Request on given user's behalf that the given nodes be started up.

        Power-on is only requested for nodes that the user has ownership
        privileges for; any other nodes in the request are ignored.

        :param ids: The `system_id` values for nodes to be started.
        :type ids: Sequence
        :param by_user: Requesting user.
        :type by_user: User_
        :param user_data: Optional blob of user-data to be made available to
            the nodes through the metadata service.  If not given, any
            previous user data is used.
        :type user_data: basestring
        :return: Those Nodes for which power-on was actually requested.
        :rtype: list
        """
        # TODO: File structure needs sorting out to avoid this circular
        # import dance.
        from metadataserver.models import NodeUserData
        nodes = self.get_nodes(by_user, NODE_PERMISSION.EDIT, ids=ids)
        processed_nodes = []
        for node in nodes:
            NodeUserData.objects.set_user_data(node, user_data)
            # Wake on LAN is a special case, deal with it first.
            if node.power_type == POWER_TYPE.WAKE_ON_LAN:
                # If power_parameters is set, use it.  Otherwise, use the
                # first registered MAC address.
                mac = None
                if node.power_parameters:
                    mac = node.power_parameters.get("mac", None)
                else:
                    try:
                        macaddress = node.macaddress_set.order_by('created')[0]
                    except IndexError:
                        pass  # No MAC recorded for this node.
                    else:
                        mac = macaddress.mac_address
                if mac is not None and mac != "":
                    power_on.delay(node.power_type, mac=mac)
                    processed_nodes.append(node)
            else:
                if node.power_parameters:
                    power_on.delay(node.power_type, **node.power_parameters)
                    processed_nodes.append(node)
        return processed_nodes


def get_db_state(instance, field_name):
    """Get the persisted state of the given field for the given instance.

    :param instance: The model instance to consider.
    :type instance: :class:`django.db.models.Model`
    :param field_name: The name of the field to return.
    :type field_name: basestring
    """
    try:
        return getattr(
            instance.__class__.objects.get(pk=instance.pk), field_name)
    except instance.DoesNotExist:
        return None


class Node(CleanSave, TimestampedModel):
    """A `Node` represents a physical machine used by the MAAS Server.

    :ivar system_id: The unique identifier for this `Node`.
        (e.g. 'node-41eba45e-4cfa-11e1-a052-00225f89f211').
    :ivar hostname: This `Node`'s hostname.
    :ivar status: This `Node`'s status. See the vocabulary
        :class:`NODE_STATUS`.
    :ivar owner: This `Node`'s owner if it's in use, None otherwise.
    :ivar after_commissioning_action: The action to perform after
        commissioning. See vocabulary
        :class:`NODE_AFTER_COMMISSIONING_ACTION`.
    :ivar power_type: The :class:`POWER_TYPE` that determines how this
        node will be powered on.  If not given, the default will be used as
        configured in the `node_power_type` setting.
    :ivar objects: The :class:`NodeManager`.

    """

    class Meta(DefaultMeta):
        """Needed for South to recognize this model."""

    system_id = CharField(
        max_length=41, unique=True, default=generate_node_system_id,
        editable=False)

    hostname = CharField(max_length=255, default='', blank=True)

    status = IntegerField(
        max_length=10, choices=NODE_STATUS_CHOICES, editable=False,
        default=NODE_STATUS.DEFAULT_STATUS)

    owner = ForeignKey(
        User, default=None, blank=True, null=True, editable=False)

    after_commissioning_action = IntegerField(
        choices=NODE_AFTER_COMMISSIONING_ACTION_CHOICES,
        default=NODE_AFTER_COMMISSIONING_ACTION.DEFAULT)

    architecture = CharField(
        max_length=10, choices=ARCHITECTURE_CHOICES, blank=False,
        default=ARCHITECTURE.i386)

    # For strings, Django insists on abusing the empty string ("blank")
    # to mean "none."
    power_type = CharField(
        max_length=10, choices=POWER_TYPE_CHOICES, null=False, blank=True,
        default=POWER_TYPE.DEFAULT)

    # JSON-encoded set of parameters for power control.
    power_parameters = JSONObjectField(blank=True, default="")

    token = ForeignKey(
        Token, db_index=True, null=True, editable=False, unique=False)

    error = CharField(max_length=255, blank=True, default='')

    objects = NodeManager()

    def __unicode__(self):
        if self.hostname:
            return "%s (%s)" % (self.system_id, self.hostname)
        else:
            return self.system_id

    def clean_status(self):
        """Check a node's status transition against the node-status FSM."""
        old_status = get_db_state(self, 'status')
        if self.status == old_status:
            # No transition is always a safe transition.
            pass
        elif self.status in NODE_TRANSITIONS.get(old_status, ()):
            # Valid transition.
            pass
        else:
            # Transition not permitted.
            error_text = "Invalid transition: %s -> %s." % (
                NODE_STATUS_CHOICES_DICT.get(old_status, "Unknown"),
                NODE_STATUS_CHOICES_DICT.get(self.status, "Unknown"),
                )
            raise NodeStateViolation(error_text)

    def clean(self, *args, **kwargs):
        super(Node, self).clean(*args, **kwargs)
        self.clean_status()

    def display_status(self):
        """Return status text as displayed to the user.

        The UI representation is taken from NODE_STATUS_CHOICES_DICT and may
        interpolate the variable "owner" to reflect the username of the node's
        current owner, if any.
        """
        status_text = NODE_STATUS_CHOICES_DICT[self.status]
        if self.status == NODE_STATUS.ALLOCATED:
            # The User is represented as its username in interpolation.
            # Don't just say self.owner.username here, or there will be
            # trouble with unowned nodes!
            return "%s to %s" % (status_text, self.owner)
        else:
            return status_text

    def add_mac_address(self, mac_address):
        """Add a new MAC address to this `Node`.

        :param mac_address: The MAC address to be added.
        :type mac_address: basestring
        :raises: django.core.exceptions.ValidationError_

        .. _django.core.exceptions.ValidationError: https://
           docs.djangoproject.com/en/dev/ref/exceptions/
           #django.core.exceptions.ValidationError
        """

        mac = MACAddress(mac_address=mac_address, node=self)
        mac.save()
        return mac

    def remove_mac_address(self, mac_address):
        """Remove a MAC address from this `Node`.

        :param mac_address: The MAC address to be removed.
        :type mac_address: str

        """
        mac = MACAddress.objects.get(mac_address=mac_address, node=self)
        if mac:
            mac.delete()

    def accept_enlistment(self, user):
        """Accept this node's (anonymous) enlistment.

        This call makes sense only on a node in Declared state, i.e. one that
        has been anonymously enlisted and is now waiting for a MAAS user to
        accept that enlistment as authentic.  Calling it on a node that is in
        Ready or Commissioning state, however, is not an error -- it probably
        just means that somebody else has beaten you to it.

        :return: This node if it has made the transition from Declared, or
            None if it was already in an accepted state.
        """
        accepted_states = [NODE_STATUS.READY, NODE_STATUS.COMMISSIONING]
        if self.status in accepted_states:
            return None
        if self.status != NODE_STATUS.DECLARED:
            raise NodeStateViolation(
                "Cannot accept node enlistment: node %s is in state %s."
                % (self.system_id, NODE_STATUS_CHOICES_DICT[self.status]))

        self.start_commissioning(user)
        return self

    def start_commissioning(self, user):
        """Install OS and self-test a new node."""
        # Avoid circular imports.
        from metadataserver.models import NodeCommissionResult

        path = settings.COMMISSIONING_SCRIPT
        if not os.path.exists(path):
            raise ValidationError(
                "Commissioning script is missing: %s" % path)
        with open(path, 'r') as f:
            commissioning_user_data = f.read()

        NodeCommissionResult.objects.clear_results(self)
        self.status = NODE_STATUS.COMMISSIONING
        self.owner = user
        self.save()
        # The commissioning profile is handled in start_nodes.
        Node.objects.start_nodes(
            [self.system_id], user, user_data=commissioning_user_data)

    def delete(self):
        # Delete the related mac addresses first.
        self.macaddress_set.all().delete()
        # Allocated nodes can't be deleted.
        if self.status == NODE_STATUS.ALLOCATED:
            raise NodeStateViolation(
                "Cannot delete node %s: node is in state %s."
                % (self.system_id, NODE_STATUS_CHOICES_DICT[self.status]))
        super(Node, self).delete()

    def set_mac_based_hostname(self, mac_address):
        mac_hostname = mac_address.replace(':', '').lower()
        domain = Config.objects.get_config("enlistment_domain")
        domain = domain.strip("." + whitespace)
        if len(domain) > 0:
            self.hostname = "node-%s.%s" % (mac_hostname, domain)
        else:
            self.hostname = "node-%s" % mac_hostname
        self.save()

    def get_effective_power_type(self):
        """Get power-type to use for this node.

        If no power type has been set for the node, get the configured
        default.
        """
        if self.power_type == POWER_TYPE.DEFAULT:
            power_type = Config.objects.get_config('node_power_type')
            if power_type == POWER_TYPE.DEFAULT:
                raise ValueError(
                    "Default power type is configured to the default, but "
                    "that means to use the configured default.  It needs to "
                    "be confirued to another, more useful value.")
        else:
            power_type = self.power_type
        return power_type

    def acquire(self, user, token=None):
        """Mark commissioned node as acquired by the given user and token."""
        assert self.owner is None
        assert token is None or token.user == user
        self.status = NODE_STATUS.ALLOCATED
        self.owner = user
        self.token = token
        self.save()

    def release(self):
        """Mark allocated or reserved node as available again."""
        self.status = NODE_STATUS.READY
        self.owner = None
        self.token = None
        self.save()


mac_re = re.compile(r'^([0-9a-fA-F]{2}:){5}[0-9a-fA-F]{2}$')


class MACAddress(CleanSave, TimestampedModel):
    """A `MACAddress` represents a `MAC address
    <http://en.wikipedia.org/wiki/MAC_address>`_ attached to a :class:`Node`.

    :ivar mac_address: The MAC address.
    :ivar node: The `Node` related to this `MACAddress`.

    """
    mac_address = MACAddressField(unique=True)
    node = ForeignKey(Node, editable=False)

    class Meta(DefaultMeta):
        verbose_name = "MAC address"
        verbose_name_plural = "MAC addresses"

    def __unicode__(self):
        return self.mac_address

    def unique_error_message(self, model_class, unique_check):
        if unique_check == ('mac_address',):
                return "This MAC address is already registered."
        return super(
            MACAddress, self).unique_error_message(model_class, unique_check)


GENERIC_CONSUMER = 'MAAS consumer'


def create_auth_token(user):
    """Create new Token and Consumer (OAuth authorisation) for `user`.

    :param user: The user to create a token for.
    :type user: User
    :return: The created Token.
    :rtype: piston.models.Token

    """
    consumer = Consumer.objects.create(
        user=user, name=GENERIC_CONSUMER, status='accepted')
    consumer.generate_random_codes()
    # This is a 'generic' consumer aimed to service many clients, hence
    # we don't authenticate the consumer with key/secret key.
    consumer.secret = ''
    consumer.save()
    token = Token.objects.create(
        user=user, token_type=Token.ACCESS, consumer=consumer,
        is_approved=True)
    token.generate_random_codes()
    return token


def get_auth_tokens(user):
    """Fetches all the user's OAuth tokens.

    :return: A QuerySet of the tokens.
    :rtype: django.db.models.query.QuerySet_

    .. _django.db.models.query.QuerySet: https://docs.djangoproject.com/
       en/dev/ref/models/querysets/

    """
    return Token.objects.select_related().filter(
        user=user, token_type=Token.ACCESS, is_approved=True).order_by('id')


# Scheduled for model migration on 2012-06-01
class UserProfileManager(Manager):
    """A utility to manage the collection of UserProfile (or User).

    This should be used when dealing with UserProfiles or Users because it
    returns only users with a profile attached to them (as opposed to system
    users who don't have a profile).
    """

    def all_users(self):
        """Returns all the "real" users (the users which are not system users
        and thus have a UserProfile object attached to them).

        :return: A QuerySet of the users.
        :rtype: django.db.models.query.QuerySet_

        .. _django.db.models.query.QuerySet: https://docs.djangoproject.com/
           en/dev/ref/models/querysets/

        """
        user_ids = UserProfile.objects.all().values_list('user', flat=True)
        return User.objects.filter(id__in=user_ids)


# Scheduled for model migration on 2012-06-01
class UserProfile(CleanSave, Model):
    """A User profile to store MAAS specific methods and fields.

    :ivar user: The related User_.

    .. _UserProfile: https://docs.djangoproject.com/
       en/dev/topics/auth/
       #storing-additional-information-about-users

    """

    class Meta(DefaultMeta):
        """Needed for South to recognize this model."""

    objects = UserProfileManager()
    user = OneToOneField(User)

    def delete(self):
        if self.user.node_set.exists():
            nb_nodes = self.user.node_set.count()
            msg = (
                "User %s cannot be deleted: it still has %d node(s) "
                "deployed." % (self.user.username, nb_nodes))
            raise CannotDeleteUserException(msg)
        self.user.consumers.all().delete()
        self.user.delete()
        super(UserProfile, self).delete()

    def get_authorisation_tokens(self):
        """Fetches all the user's OAuth tokens.

        :return: A QuerySet of the tokens.
        :rtype: django.db.models.query.QuerySet_

        .. _django.db.models.query.QuerySet: https://docs.djangoproject.com/
           en/dev/ref/models/querysets/

        """
        return get_auth_tokens(self.user)

    def create_authorisation_token(self):
        """Create a new Token and its related Consumer (OAuth authorisation).

        :return: A tuple containing the Consumer and the Token that were
            created.
        :rtype: tuple

        """
        token = create_auth_token(self.user)
        return token.consumer, token

    def delete_authorisation_token(self, token_key):
        """Delete the user's OAuth token wich key token_key.

        :param token_key: The key of the token to be deleted.
        :type token_key: str
        :raises: django.http.Http404_

        """
        token = get_object_or_404(
            Token, user=self.user, token_type=Token.ACCESS, key=token_key)
        token.consumer.delete()
        token.delete()

    def __unicode__(self):
        return self.user.username


# When a user is created: create the related profile and the default
# consumer/token.
def create_user(sender, instance, created, **kwargs):
    # System users do not have profiles.
    if created and instance.username not in SYSTEM_USERS:
        # Create related UserProfile.
        profile = UserProfile.objects.create(user=instance)

        # Create initial authorisation token.
        profile.create_authorisation_token()

# Connect the 'create_user' method to the post save signal of User.
post_save.connect(create_user, sender=User)


# Monkey patch django.contrib.auth.models.User to force email to be unique.
User._meta.get_field('email')._unique = True


# Due for model migration on 2012-05-25
class SSHKeyManager(Manager):
    """A utility to manage the colletion of `SSHKey`s."""

    def get_keys_for_user(self, user):
        """Return the text of the ssh keys associated with a user."""
        return SSHKey.objects.filter(user=user).values_list('key', flat=True)


# Due for model migration on 2012-05-25
def validate_ssh_public_key(value):
    """Validate that the given value contains a valid SSH public key."""
    try:
        key = Key.fromString(value)
        if not key.isPublic():
            raise ValidationError(
                "Invalid SSH public key (this key is a private key).")
    except (BadKeyError, binascii.Error):
        raise ValidationError("Invalid SSH public key.")


# Due for model migration on 2012-05-25
HELLIPSIS = '&hellip;'


# Due for model migration on 2012-05-25
def get_html_display_for_key(key, size):
    """Return a compact HTML representation of this key with a boundary on
    the size of the resulting string.

    A key typically looks like this: 'key_type key_string comment'.
    What we want here is display the key_type and, if possible (i.e. if it
    fits in the boundary that `size` gives us), the comment.  If possible we
    also want to display a truncated key_string.  If the comment is too big
    to fit in, we simply display a cropped version of the whole string.

    :param key: The key for which we want an HTML representation.
    :type name: basestring
    :param size: The maximum size of the representation.  This may not be
        met exactly.
    :type size: int
    :return: The HTML representation of this key.
    :rtype: basestring
    """
    key = key.strip()
    key_parts = key.split(' ', 2)

    if len(key_parts) == 3:
        key_type = key_parts[0]
        key_string = key_parts[1]
        comment = key_parts[2]
        room_for_key = (
            size - (len(key_type) + len(comment) + len(HELLIPSIS) + 2))
        if room_for_key > 0:
            return '%s %.*s%s %s' % (
                escape(key_type, quote=True),
                room_for_key,
                escape(key_string, quote=True),
                HELLIPSIS,
                escape(comment, quote=True))

    if len(key) > size:
        return '%.*s%s' % (
            size - len(HELLIPSIS),
            escape(key, quote=True),
            HELLIPSIS)
    else:
        return escape(key, quote=True)


# Due for model migration on 2012-05-25
MAX_KEY_DISPLAY = 50


# Due for model migration on 2012-05-25
class SSHKey(CleanSave, TimestampedModel):
    """A `SSHKey` represents a user public SSH key.

    Users will be able to access `Node`s using any of their registered keys.

    :ivar user: The user which owns the key.
    :ivar key: The ssh public key.
    """

    objects = SSHKeyManager()

    user = ForeignKey(User, null=False, editable=False)

    key = TextField(
        null=False, editable=True, validators=[validate_ssh_public_key])

    class Meta(DefaultMeta):
        verbose_name = "SSH key"
        unique_together = ('user', 'key')

    def unique_error_message(self, model_class, unique_check):
        if unique_check == ('user', 'key'):
                return "This key has already been added for this user."
        return super(
            SSHKey, self).unique_error_message(model_class, unique_check)

    def __unicode__(self):
        return self.key

    def display_html(self):
        """Return a compact HTML representation of this key.

        :return: The HTML representation of this key.
        :rtype: basestring
        """
        return mark_safe(get_html_display_for_key(self.key, MAX_KEY_DISPLAY))


# Register the models in the admin site.
admin.site.register(Consumer)
admin.site.register(Config)
admin.site.register(FileStorage)
admin.site.register(MACAddress)
admin.site.register(Node)
admin.site.register(SSHKey)


class MAASAuthorizationBackend(ModelBackend):

    supports_object_permissions = True

    def has_perm(self, user, perm, obj=None):
        # Note that a check for a superuser will never reach this code
        # because Django will return True (as an optimization) for every
        # permission check performed on a superuser.
        if not user.is_active:
            # Deactivated users, and in particular the node-init user,
            # are prohibited from accessing maasserver services.
            return False

        # Only Nodes can be checked. We also don't support perm checking
        # when obj = None.
        if not isinstance(obj, Node):
            raise NotImplementedError(
                'Invalid permission check (invalid object type).')

        if perm == NODE_PERMISSION.VIEW:
            return obj.owner in (None, user)
        elif perm == NODE_PERMISSION.EDIT:
            return obj.owner == user
        elif perm == NODE_PERMISSION.ADMIN:
            # 'admin_node' permission is solely granted to superusers.
            return False
        else:
            raise NotImplementedError(
                'Invalid permission check (invalid permission name: %s).' %
                    perm)


# 'provisioning' is imported so that it can register its signal handlers early
# on, before it misses anything.
from maasserver import provisioning
# We mention 'provisioning' here to silence lint warnings.
provisioning

from maasserver import messages
messages
