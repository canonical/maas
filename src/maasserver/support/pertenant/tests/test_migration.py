# Copyright 2013-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test `maasserver.support.pertenant.migration."""

from unittest.mock import call, sentinel

from django.contrib.auth.models import User

from maasserver.models import Node, SSHKey
from maasserver.support.pertenant import migration
from maasserver.support.pertenant.migration import (
    copy_ssh_keys,
    get_destination_user,
    get_legacy_user,
    get_owned_nodes,
    get_owned_nodes_owners,
    get_real_users,
    get_ssh_keys,
    get_unowned_files,
    give_api_credentials_to_user,
    give_file_to_user,
    give_node_to_user,
    legacy_user_name,
    migrate,
    migrate_to_user,
)
from maasserver.support.pertenant.tests.test_utils import (
    make_provider_state_file,
)
from maasserver.testing import get_data
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.utils.orm import reload_object


def get_ssh_key_string(num=0):
    return get_data("data/test_rsa%d.pub" % num)


class TestFunctions(MAASServerTestCase):
    def find_legacy_user(self):
        return User.objects.filter(username=legacy_user_name)

    def test_get_legacy_user_creates_user(self):
        self.assertEqual([], list(self.find_legacy_user()))
        legacy_user = get_legacy_user()
        self.assertEqual([legacy_user], list(self.find_legacy_user()))
        self.assertEqual(legacy_user.first_name, "Shared")
        self.assertEqual(legacy_user.last_name, "Environment")
        self.assertEqual(legacy_user.email, legacy_user_name + "@localhost")
        self.assertTrue(legacy_user.is_active)

    def test_get_legacy_user_creates_user_only_once(self):
        legacy_user1 = get_legacy_user()
        self.assertEqual([legacy_user1], list(self.find_legacy_user()))
        legacy_user2 = get_legacy_user()
        self.assertEqual([legacy_user2], list(self.find_legacy_user()))
        self.assertEqual(legacy_user1, legacy_user2)

    def test_get_unowned_files_no_files(self):
        self.assertEqual([], list(get_unowned_files()))

    def test_get_unowned_files(self):
        user = factory.make_User()
        files = [
            factory.make_FileStorage(owner=None),
            factory.make_FileStorage(owner=user),
            factory.make_FileStorage(owner=None),
        ]
        self.assertEqual({files[0], files[2]}, set(get_unowned_files()))

    def test_get_real_users_no_users(self):
        get_legacy_user()  # Ensure at least the legacy user exists.
        self.assertEqual([], list(get_real_users()))

    def test_get_real_users(self):
        get_legacy_user()  # Ensure at least the legacy user exists.
        users = [factory.make_User(), factory.make_User()]
        self.assertEqual(set(users), set(get_real_users()))

    def test_get_owned_nodes_no_nodes(self):
        self.assertEqual([], list(get_owned_nodes()))

    def test_get_owned_nodes_no_owned_nodes(self):
        factory.make_Node()
        self.assertEqual([], list(get_owned_nodes()))

    def test_get_owned_nodes_with_owned_nodes(self):
        nodes = {
            factory.make_Node(owner=factory.make_User()),
            factory.make_Node(owner=factory.make_User()),
        }
        self.assertEqual(nodes, set(get_owned_nodes()))

    def test_get_owned_nodes_with_nodes_owned_by_system_users(self):
        (factory.make_Node(owner=get_legacy_user()),)
        self.assertEqual([], list(get_owned_nodes()))

    def test_get_owned_nodes_owners_no_users(self):
        self.assertEqual([], list(get_owned_nodes_owners()))

    def test_get_owned_nodes_owners_no_nodes(self):
        factory.make_User()
        self.assertEqual([], list(get_owned_nodes_owners()))

    def test_get_owned_nodes_owners_no_owned_nodes(self):
        factory.make_User()
        factory.make_Node(owner=None)
        self.assertEqual([], list(get_owned_nodes_owners()))

    def test_get_owned_nodes_owners(self):
        user1 = factory.make_User()
        user2 = factory.make_User()
        factory.make_User()
        factory.make_Node(owner=user1)
        factory.make_Node(owner=user2)
        factory.make_Node(owner=None)
        self.assertEqual({user1, user2}, set(get_owned_nodes_owners()))

    def test_get_destination_user_one_real_user(self):
        user = factory.make_User()
        self.assertEqual(user, get_destination_user())

    def test_get_destination_user_two_real_users(self):
        factory.make_User()
        factory.make_User()
        self.assertEqual(get_legacy_user(), get_destination_user())

    def test_get_destination_user_no_real_users(self):
        self.assertEqual(get_legacy_user(), get_destination_user())

    def test_get_destination_user_with_user_from_juju_state(self):
        user = factory.make_User()
        # Also create another user.
        factory.make_User()
        node = factory.make_Node(owner=user)
        make_provider_state_file(node)
        self.assertEqual(user, get_destination_user())

    def test_get_destination_user_with_orphaned_juju_state(self):
        user = factory.make_User()
        # Also create another user.
        factory.make_User()
        node = factory.make_Node(owner=user)
        make_provider_state_file(node)
        node.delete()  # Orphan the state.
        self.assertEqual(get_legacy_user(), get_destination_user())


class TestCopySSHKeys(MAASServerTestCase):
    """Tests for copy_ssh_keys()."""

    def test_noop_when_there_are_no_keys(self):
        user1 = factory.make_User()
        user2 = factory.make_User()
        copy_ssh_keys(user1, user2)
        ssh_keys = SSHKey.objects.filter(user__in={user1, user2})
        self.assertEqual([], list(ssh_keys))

    def test_copy(self):
        user1 = factory.make_User()
        key1 = factory.make_SSHKey(user1)
        user2 = factory.make_User()
        copy_ssh_keys(user1, user2)
        user2s_ssh_keys = SSHKey.objects.filter(user=user2)
        self.assertEqual(
            {key1.key}, {ssh_key.key for ssh_key in user2s_ssh_keys}
        )

    def test_copy_is_idempotent(self):
        # When the destination user already has a key, copy_ssh_keys() is a
        # noop for that key.
        user1 = factory.make_User()
        key1 = factory.make_SSHKey(user1)
        user2 = factory.make_User()
        key2 = factory.make_SSHKey(user2, key1.key)
        copy_ssh_keys(user1, user2)
        user2s_ssh_keys = SSHKey.objects.filter(user=user2)
        self.assertEqual(
            {key2.key}, {ssh_key.key for ssh_key in user2s_ssh_keys}
        )

    def test_copy_does_not_clobber(self):
        # When the destination user already has some keys, copy_ssh_keys()
        # adds to them; it does not remove them.
        user1 = factory.make_User()
        key1 = factory.make_SSHKey(user1, get_ssh_key_string(1))
        user2 = factory.make_User()
        key2 = factory.make_SSHKey(user2, get_ssh_key_string(2))
        copy_ssh_keys(user1, user2)
        user2s_ssh_keys = SSHKey.objects.filter(user=user2)
        self.assertEqual(
            {key1.key, key2.key}, {ssh_key.key for ssh_key in user2s_ssh_keys}
        )


class TestGiveFileToUser(MAASServerTestCase):
    def test_give_unowned_file(self):
        user = factory.make_User()
        file = factory.make_FileStorage(owner=None)
        give_file_to_user(file, user)
        self.assertEqual(user, file.owner)

    def test_give_owned_file(self):
        user1 = factory.make_User()
        user2 = factory.make_User()
        file = factory.make_FileStorage(owner=user1)
        give_file_to_user(file, user2)
        self.assertEqual(user2, file.owner)

    def test_file_saved(self):
        user = factory.make_User()
        file = factory.make_FileStorage(owner=None)
        save = self.patch(file, "save")
        give_file_to_user(file, user)
        save.assert_called_once_with()


class TestGiveCredentialsToUser(MAASServerTestCase):
    def test_give(self):
        user1 = factory.make_User()
        user2 = factory.make_User()
        profile = user1.userprofile
        consumer, token = profile.create_authorisation_token()
        give_api_credentials_to_user(user1, user2)
        self.assertEqual(user2, reload_object(consumer).user)
        self.assertEqual(user2, reload_object(token).user)


class TestGiveNodeToUser(MAASServerTestCase):
    def test_give(self):
        user1 = factory.make_User()
        user2 = factory.make_User()
        node = factory.make_Node(owner=user1)
        give_node_to_user(node, user2)
        self.assertEqual(user2, reload_object(node).owner)


class TestMigrateToUser(MAASServerTestCase):
    def test_migrate(self):
        # This is a mechanical test, to demonstrate that migrate_to_user() is
        # wired up correctly: it should not really contain much logic because
        # it is meant only as a convenient wrapper around other functions.
        # Those functions are unit tested individually, and the overall
        # behaviour of migrate() is tested too; this is another layer of
        # verification. It's also a reminder not to stuff logic into
        # migrate_to_user(); extract it into functions instead and unit test
        # those.

        # migrate_to_user() will give all unowned files to a specified user.
        get_unowned_files = self.patch(migration, "get_unowned_files")
        get_unowned_files.return_value = [sentinel.file1, sentinel.file2]
        give_file_to_user = self.patch(migration, "give_file_to_user")
        # migrate_to_user() will copy all SSH keys and give all API
        # credentials belonging to node owners over to a specified user.
        get_owned_nodes_owners = self.patch(
            migration, "get_owned_nodes_owners"
        )
        get_owned_nodes_owners.return_value = [
            sentinel.node_owner1,
            sentinel.node_owner2,
        ]
        copy_ssh_keys = self.patch(migration, "copy_ssh_keys")
        give_api_credentials_to_user = self.patch(
            migration, "give_api_credentials_to_user"
        )
        # migrate_to_user() will give all owned nodes to a specified user.
        get_owned_nodes = self.patch(migration, "get_owned_nodes")
        get_owned_nodes.return_value = [sentinel.node1, sentinel.node2]
        give_node_to_user = self.patch(migration, "give_node_to_user")

        migrate_to_user(sentinel.user)

        # Each unowned file is given to the destination user one at a time.
        get_unowned_files.assert_called_once_with()
        self.assertEqual(
            [
                call(sentinel.file1, sentinel.user),
                call(sentinel.file2, sentinel.user),
            ],
            give_file_to_user.call_args_list,
        )
        # The SSH keys of each node owner are copied to the destination user,
        # one at a time, and the credentials of these users are given to the
        # destination user.
        get_owned_nodes_owners.assert_called_once_with()
        self.assertEqual(
            [
                call(sentinel.node_owner1, sentinel.user),
                call(sentinel.node_owner2, sentinel.user),
            ],
            copy_ssh_keys.call_args_list,
        )
        self.assertEqual(
            [
                call(sentinel.node_owner1, sentinel.user),
                call(sentinel.node_owner2, sentinel.user),
            ],
            give_api_credentials_to_user.call_args_list,
        )
        # Each owned node is given to the destination user one at a time.
        get_owned_nodes.assert_called_once_with()
        self.assertEqual(
            [
                call(sentinel.node1, sentinel.user),
                call(sentinel.node2, sentinel.user),
            ],
            give_node_to_user.call_args_list,
        )


class TestMigrate(MAASServerTestCase):
    def test_migrate_runs_when_no_files_exist(self):
        migrate()

    def test_migrate_runs_when_no_unowned_files_exist(self):
        factory.make_FileStorage(owner=factory.make_User())
        migrate()

    def test_migrate_all_files_to_single_user_when_only_one_user(self):
        user = factory.make_User()
        stored = factory.make_FileStorage(owner=None)
        migrate()
        self.assertEqual(user, reload_object(stored).owner)

    def test_migrate_all_files_to_new_legacy_user_when_multiple_users(self):
        stored = factory.make_FileStorage(owner=None)
        user1 = factory.make_User()
        user2 = factory.make_User()
        migrate()
        stored = reload_object(stored)
        self.assertNotIn(stored.owner, {user1, user2, None})

    def test_migrate_all_nodes_to_new_legacy_user_when_multiple_users(self):
        factory.make_FileStorage(owner=None)
        user1 = factory.make_User()
        node1 = factory.make_Node(owner=user1)
        user2 = factory.make_User()
        node2 = factory.make_Node(owner=user2)
        migrate()
        self.assertNotIn(reload_object(node1).owner, {user1, user2, None})
        self.assertNotIn(reload_object(node2).owner, {user1, user2, None})

    def test_migrate_all_nodes_to_bootstrap_owner_when_multiple_users(self):
        user1 = factory.make_User()
        node1 = factory.make_Node(owner=user1)
        user2 = factory.make_User()
        node2 = factory.make_Node(owner=user2)
        make_provider_state_file(node1)
        migrate()
        self.assertEqual(
            (user1, user1),
            (reload_object(node1).owner, reload_object(node2).owner),
        )

    def test_migrate_ancillary_data_to_legacy_user_when_multiple_users(self):
        factory.make_FileStorage(owner=None)
        # Create two users, both with API credentials, an SSH key and a node.
        user1 = factory.make_User()
        consumer1, token1 = user1.userprofile.create_authorisation_token()
        key1 = factory.make_SSHKey(user1, get_ssh_key_string(1))
        node1 = factory.make_Node(owner=user1)
        user2 = factory.make_User()
        consumer2, token2 = user2.userprofile.create_authorisation_token()
        key2 = factory.make_SSHKey(user2, get_ssh_key_string(2))
        node2 = factory.make_Node(owner=user2)
        migrate()
        # The SSH keys have been copied to the legacy user.
        legacy_user = get_legacy_user()
        legacy_users_ssh_keys = get_ssh_keys(legacy_user)
        self.assertEqual({key1.key, key2.key}, set(legacy_users_ssh_keys))
        # The API credentials have been moved to the legacy user.
        legacy_users_nodes = Node.objects.filter(owner=legacy_user)
        self.assertEqual({node1, node2}, set(legacy_users_nodes))
        self.assertEqual(
            (legacy_user, legacy_user, legacy_user, legacy_user),
            (
                reload_object(consumer1).user,
                reload_object(token1).user,
                reload_object(consumer2).user,
                reload_object(token2).user,
            ),
        )
