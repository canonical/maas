# Copyright 2012-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""System user representing node-group workers.

Workers access the MAAS API under this user identity.
"""


from django.contrib.auth.models import User

user_name = "MAAS"


def get_worker_user():
    """Get the system user representing the rack controller workers."""
    worker_user, created = User.objects.get_or_create(
        username=user_name,
        defaults=dict(
            first_name="MAAS",
            last_name="Special user",
            email="maas@localhost",
            is_staff=False,
            is_superuser=True,
        ),
    )
    return worker_user
