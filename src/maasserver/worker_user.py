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
from django.core.cache import cache


user_name = 'maas-nodegroup-worker'

# Cache key for the worker user.
WORKER_USER_CACHE_KEY = 'worker-user-maas-cache-key'


def get_worker_user():
    """Get the system user representing the node-group workers."""
    worker_user = cache.get(WORKER_USER_CACHE_KEY)
    if worker_user is None:
        worker_user, created = User.objects.get_or_create(
            username=user_name, defaults=dict(
                first_name="Node-group worker",
                last_name="Special user",
                email="maas-nodegroup-worker@localhost",
                is_staff=False, is_active=False, is_superuser=False))
        cache.set(WORKER_USER_CACHE_KEY, worker_user)
    return worker_user
