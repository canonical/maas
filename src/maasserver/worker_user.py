# Copyright 2012-2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""System user representing node-group workers.

Workers access the MAAS API under this user identity.
"""

from django.contrib.auth.models import User

from maascommon.constants import (
    MAAS_USER_EMAIL,
    MAAS_USER_LAST_NAME,
    MAAS_USER_USERNAME,
)


def get_worker_user():
    """Get the system user representing the rack controller workers."""
    worker_user, created = User.objects.get_or_create(
        username=MAAS_USER_USERNAME,
        defaults=dict(
            first_name=MAAS_USER_USERNAME,
            last_name=MAAS_USER_LAST_NAME,
            email=MAAS_USER_EMAIL,
            is_staff=False,
            is_superuser=True,
        ),
    )
    return worker_user
