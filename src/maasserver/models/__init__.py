# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Model helpers and state for maasserver."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    'BootImage',
    'ComponentError',
    'Config',
    'DHCPLease',
    'DownloadProgress',
    'FileStorage',
    'logger',
    'MACAddress',
    'Node',
    'NodeGroup',
    'NodeGroupInterface',
    'SSHKey',
    'Tag',
    'UserProfile',
    'Zone',
    ]

from django.contrib import admin
from django.contrib.auth.backends import ModelBackend
from django.contrib.auth.models import User
from django.core.urlresolvers import (
    get_callable,
    get_resolver,
    get_script_prefix,
    )
from django.db.models.signals import post_save
from maasserver import logger
from maasserver.enum import NODE_PERMISSION
from maasserver.models.bootimage import BootImage
from maasserver.models.component_error import ComponentError
from maasserver.models.config import Config
from maasserver.models.dhcplease import DHCPLease
from maasserver.models.downloadprogress import DownloadProgress
from maasserver.models.filestorage import FileStorage
from maasserver.models.macaddress import MACAddress
from maasserver.models.node import Node
from maasserver.models.nodegroup import NodeGroup
from maasserver.models.nodegroupinterface import NodeGroupInterface
from maasserver.models.sshkey import SSHKey
from maasserver.models.tag import Tag
from maasserver.models.user import create_user
from maasserver.models.userprofile import UserProfile
from maasserver.models.zone import Zone
from maasserver.utils import ignore_unused
from piston.doc import HandlerDocumentation
from piston.models import Consumer

# Suppress warning about symbols being imported, but only used for
# export in __all__.
ignore_unused(
    ComponentError, Config, DHCPLease, FileStorage, MACAddress, NodeGroup,
    SSHKey, Tag, UserProfile, NodeGroupInterface)


# Connect the 'create_user' method to the post save signal of User.
post_save.connect(create_user, sender=User)


# Monkey patch django.contrib.auth.models.User to force email to be unique.
User._meta.get_field('email')._unique = True


# Monkey patch piston's usage of Django's get_resolver to be compatible
# with Django 1.4.
# XXX: rvb 2012-09-21 bug=1054040
# See https://bitbucket.org/jespern/django-piston/issue/218 for details.
def get_resource_uri_template(self):
    """
    URI template processor.
    See http://bitworking.org/projects/URI-Templates/
    """
    def _convert(template, params=[]):
        """URI template converter"""
        paths = template % dict([p, "{%s}" % p] for p in params)
        return u'%s%s' % (get_script_prefix(), paths)
    try:
        resource_uri = self.handler.resource_uri()
        components = [None, [], {}]

        for i, value in enumerate(resource_uri):
            components[i] = value
        lookup_view, args, kwargs = components
        lookup_view = get_callable(lookup_view, True)

        possibilities = get_resolver(None).reverse_dict.getlist(lookup_view)
        # The monkey patch is right here: we need to cope with 'possibilities'
        # being a list of tuples with 2 or 3 elements.
        for possibility_data in possibilities:
            possibility = possibility_data[0]
            for result, params in possibility:
                if args:
                    if len(args) != len(params):
                        continue
                    return _convert(result, params)
                else:
                    if set(kwargs.keys()) != set(params):
                        continue
                    return _convert(result, params)
    except:
        return None


HandlerDocumentation.get_resource_uri_template = get_resource_uri_template

# Monkey patch the property resource_uri_template: it hold a reference to
# get_resource_uri_template.
HandlerDocumentation.resource_uri_template = (
    property(get_resource_uri_template))


# Register the models in the admin site.
admin.site.register(BootImage)
admin.site.register(Config)
admin.site.register(Consumer)
admin.site.register(DownloadProgress)
admin.site.register(FileStorage)
admin.site.register(MACAddress)
admin.site.register(Node)
admin.site.register(Tag)
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
            # Any registered user can view a node regardless of its state.
            return True
        elif perm == NODE_PERMISSION.EDIT:
            return obj.owner == user
        elif perm == NODE_PERMISSION.ADMIN:
            # 'admin_node' permission is solely granted to superusers.
            return False
        else:
            raise NotImplementedError(
                'Invalid permission check (invalid permission name: %s).' %
                perm)


from maasserver import messages
ignore_unused(messages)

from maasserver import dns_connect
ignore_unused(dns_connect)

from maasserver import dhcp_connect
ignore_unused(dhcp_connect)
