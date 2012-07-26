# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Model helpers and state for maasserver."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = [
    'Config',
    'DHCPLease',
    'FileStorage',
    'logger',
    'MACAddress',
    'Node',
    'NodeGroup',
    'SSHKey',
    'UserProfile',
    ]

from logging import getLogger

from django.contrib import admin
from django.contrib.auth.backends import ModelBackend
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from maasserver.enum import NODE_PERMISSION
from maasserver.models.config import Config
from maasserver.models.dhcplease import DHCPLease
from maasserver.models.filestorage import FileStorage
from maasserver.models.macaddress import MACAddress
from maasserver.models.node import Node
from maasserver.models.nodegroup import NodeGroup
from maasserver.models.sshkey import SSHKey
from maasserver.models.user import create_user
from maasserver.models.userprofile import UserProfile
from maasserver.utils import ignore_unused
from piston.models import Consumer


logger = getLogger('maasserver')


# Suppress warning about symbols being imported, but only used for
# export in __all__.
ignore_unused(
    Config, DHCPLease, FileStorage, MACAddress, NodeGroup, SSHKey,
    UserProfile)


# Connect the 'create_user' method to the post save signal of User.
post_save.connect(create_user, sender=User)


# Monkey patch django.contrib.auth.models.User to force email to be unique.
User._meta.get_field('email')._unique = True


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
ignore_unused(provisioning)

from maasserver import messages
ignore_unused(messages)

from maasserver import dns
ignore_unused(dns)
