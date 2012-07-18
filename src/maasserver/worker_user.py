# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""System user representing node-group workers.

The Celery workers access the MAAS API under this user identity.
"""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = [
    'get_worker_user',
    'user_name',
    ]

from django.contrib.auth.models import User


user_name = 'maas-nodegroup-worker'


# Cached, shared reference to this special user.  Keep internal to this
# module.
worker_user = None


def get_worker_user():
    """Get the system user representing the node-group workers."""
    global worker_user
    if worker_user is None:
        worker_user = User.objects.get(username=user_name)
    return worker_user
