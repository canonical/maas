# Copyright 2013-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Shared namespace --> per-tenant namespace migration.

Perform the following steps to migrate:

1. When no files exist (i.e. no Juju environments exist): do nothing
1a. When no *unowned* files exist: do nothing.

2. When there's only one user: assign ownership of all files to user.

3. When there are multiple users and a `provider-state` file: parse that file
   to extract the instance id of the bootstrap node. From that instance id,
   get the identity of the user who deployed this environment (that's the
   owner of the bootstrap node). Then proceed as in 4, using that user as the
   "legacy" user.

4. When there are multiple users: create a new "legacy" user, assign ownership
   of all files and allocated/owned nodes to this user, copy all public SSH
   keys to this user, and move all API credentials to this user.

There's not a lot we can do about SSH keys authorised to connect to the
already deployed nodes in #3, but this set will only ever decrease: nodes
allocated after this migration will permit access from any of the users with
SSH keys prior to the migration.
"""

from django.contrib.auth.models import User

from maasserver.models import FileStorage, Node, SSHKey
from maasserver.models.user import get_auth_tokens, SYSTEM_USERS
from maasserver.support.pertenant.utils import get_bootstrap_node_owner
from maasserver.utils.orm import get_one

legacy_user_name = "shared-environment"


def get_legacy_user():
    """Return the legacy namespace user, creating it if need be."""
    try:
        legacy_user = User.objects.get(username=legacy_user_name)
    except User.DoesNotExist:
        # Create the legacy user with a local, probably non-working, email
        # address, and an unusable password.
        legacy_user = User.objects.create_user(
            email="%s@localhost" % legacy_user_name, username=legacy_user_name
        )
        legacy_user.first_name = "Shared"
        legacy_user.last_name = "Environment"
        legacy_user.is_active = True
    return legacy_user


def get_unowned_files():
    """Returns a `QuerySet` of unowned files."""
    return FileStorage.objects.filter(owner=None)


def get_real_users():
    """Returns a `QuerySet` of real. not system, users."""
    users = User.objects.exclude(username__in=SYSTEM_USERS)
    users = users.exclude(username=legacy_user_name)
    return users


def get_owned_nodes():
    """Returns a `QuerySet` of nodes owned by real users."""
    return Node.objects.filter(owner__in=get_real_users())


def get_owned_nodes_owners():
    """Returns a `QuerySet` of the owners of nodes owned by real users."""
    owner_ids = get_owned_nodes().values_list("owner", flat=True)
    return User.objects.filter(id__in=owner_ids.distinct())


def get_destination_user():
    """Return the user to which resources should be assigned."""
    real_users = get_real_users()
    if real_users.count() == 1:
        return get_one(real_users)
    else:
        bootstrap_user = get_bootstrap_node_owner()
        if bootstrap_user is None:
            return get_legacy_user()
        else:
            return bootstrap_user


def get_ssh_keys(user):
    """Return the SSH key strings belonging to the specified user."""
    return SSHKey.objects.filter(user=user).values_list("key", flat=True)


def copy_ssh_keys(user_from, user_dest):
    """Copies SSH keys from one user to another.

    This is idempotent, and does not clobber the destination user's existing
    keys.
    """
    user_from_keys = get_ssh_keys(user_from)
    user_dest_keys = get_ssh_keys(user_dest)
    for key in set(user_from_keys).difference(user_dest_keys):
        ssh_key = SSHKey(user=user_dest, key=key)
        ssh_key.save()


def give_file_to_user(file, user):
    """Give a file to a user."""
    file.owner = user
    file.save()


def give_api_credentials_to_user(user_from, user_dest):
    """Gives one user's API credentials to another.

    This ensures that users of the shared namespace environment continue to
    operate within the legacy shared namespace environment by default via the
    API (e.g. from the command-line client, or from Juju).
    """
    for token in get_auth_tokens(user_from):
        consumer = token.consumer
        consumer.user = user_dest
        consumer.save()
        token.user = user_dest
        token.save()


def give_node_to_user(node, user):
    """Changes a node's ownership for the legacy shared environment."""
    node.owner = user
    node.save()


def migrate_to_user(user):
    """Migrate files and nodes to the specified user.

    This also copies, to the destination user, the public SSH keys of any
    owned nodes' owners. This is so that those users who had allocated nodes
    (i.e. active users of a shared-namespace environment) can access newly
    created nodes in the legacy shared-namespace environment.
    """
    for unowned_file in get_unowned_files():
        give_file_to_user(unowned_file, user)
    for node_owner in get_owned_nodes_owners():
        copy_ssh_keys(node_owner, user)
        give_api_credentials_to_user(node_owner, user)
    for owned_node in get_owned_nodes():
        give_node_to_user(owned_node, user)


def migrate():
    """Migrate files to a per-tenant namespace."""
    if get_unowned_files().exists():
        # 2, 3, and 4
        user = get_destination_user()
        migrate_to_user(user)
    else:
        # 1 and 1a
        pass
