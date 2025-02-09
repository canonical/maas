# Copyright 2012-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""User management for nodes' access to the metadata service."""

from django.contrib.auth.models import User

user_name = "maas-init-node"


def get_node_init_user():
    node_init_user, _ = User.objects.get_or_create(
        username=user_name,
        defaults=dict(
            first_name="Node-init user",
            last_name="Special user",
            email="node-init-user@localhost",
            is_staff=False,
            is_superuser=False,
            is_active=False,
        ),
    )
    return node_init_user
