# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""User management for nodes' access to the metadata service."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    'get_node_init_user',
    'user_name',
    ]

from django.contrib.auth.models import User


user_name = 'maas-init-node'


# Cached, shared reference to this special user.  Keep internal to this
# module.
node_init_user = None


def get_node_init_user():
    global node_init_user
    if node_init_user is None:
        node_init_user = User.objects.get(username=user_name)
    return node_init_user
