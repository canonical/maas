# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test maasserver models."""

from __future__ import (
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = []

import codecs
from io import BytesIO
import os
import shutil
from socket import gethostname

from django.conf import settings
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from fixtures import TestWithFixtures
from maasserver.exceptions import (
    CannotDeleteUserException,
    PermissionDenied,
    )
from maasserver.models import (
    Config,
    create_auth_token,
    DEFAULT_CONFIG,
    FileStorage,
    GENERIC_CONSUMER,
    get_auth_tokens,
    get_default_config,
    MACAddress,
    Node,
    NODE_STATUS,
    NODE_STATUS_CHOICES_DICT,
    SSHKey,
    SYSTEM_USERS,
    UserProfile,
    )
from maasserver.provisioning import get_provisioning_api_proxy
from maasserver.testing.enum import map_enum
from maasserver.testing.factory import factory
from maasserver.testing.testcase import TestCase
from metadataserver.models import NodeUserData
from piston.models import (
    Consumer,
    KEY_SIZE,
    SECRET_SIZE,
    Token,
    )
from provisioningserver.enum import POWER_TYPE
from testtools.matchers import (
    GreaterThan,
    LessThan,
    )


class NodeTest(TestCase):

    def test_system_id(self):
        """
        The generated system_id looks good.

        """
        node = factory.make_node()
        self.assertEqual(len(node.system_id), 41)
        self.assertTrue(node.system_id.startswith('node-'))

    def test_display_status(self):
        node = factory.make_node()
        self.assertEqual(
            NODE_STATUS_CHOICES_DICT[NODE_STATUS.DEFAULT_STATUS],
            node.display_status())

    def test_add_node_with_token(self):
        user = factory.make_user()
        token = create_auth_token(user)
        node = factory.make_node(token=token)
        self.assertEqual(token, node.token)

    def test_add_mac_address(self):
        node = factory.make_node()
        node.add_mac_address('AA:BB:CC:DD:EE:FF')
        macs = MACAddress.objects.filter(
            node=node, mac_address='AA:BB:CC:DD:EE:FF').count()
        self.assertEqual(1, macs)

    def test_remove_mac_address(self):
        node = factory.make_node()
        node.add_mac_address('AA:BB:CC:DD:EE:FF')
        node.remove_mac_address('AA:BB:CC:DD:EE:FF')
        macs = MACAddress.objects.filter(
            node=node, mac_address='AA:BB:CC:DD:EE:FF').count()
        self.assertEqual(0, macs)

    def test_delete_node_deletes_related_mac(self):
        node = factory.make_node()
        mac = node.add_mac_address('AA:BB:CC:DD:EE:FF')
        node.delete()
        self.assertRaises(
            MACAddress.DoesNotExist, MACAddress.objects.get, id=mac.id)

    def test_set_mac_based_hostname(self):
        node = factory.make_node()
        node.set_mac_based_hostname('AA:BB:CC:DD:EE:FF')
        hostname = 'node-aabbccddeeff'
        self.assertEqual(hostname, node.hostname)

    def test_get_effective_power_type_defaults_to_config(self):
        power_types = list(map_enum(POWER_TYPE).values())
        power_types.remove(POWER_TYPE.DEFAULT)
        node = factory.make_node(power_type=POWER_TYPE.DEFAULT)
        effective_types = []
        for power_type in power_types:
            Config.objects.set_config('node_power_type', power_type)
            effective_types.append(node.get_effective_power_type())
        self.assertEqual(power_types, effective_types)

    def test_get_effective_power_type_reads_node_field(self):
        power_types = list(map_enum(POWER_TYPE).values())
        power_types.remove(POWER_TYPE.DEFAULT)
        nodes = [
            factory.make_node(power_type=power_type)
            for power_type in power_types]
        self.assertEqual(
            power_types, [node.get_effective_power_type() for node in nodes])

    def test_get_effective_power_type_rejects_default_as_config_value(self):
        node = factory.make_node(power_type=POWER_TYPE.DEFAULT)
        Config.objects.set_config('node_power_type', POWER_TYPE.DEFAULT)
        self.assertRaises(ValueError, node.get_effective_power_type)

    def test_acquire(self):
        node = factory.make_node(status=NODE_STATUS.READY)
        user = factory.make_user()
        token = create_auth_token(user)
        node.acquire(token)
        self.assertEqual(user, node.owner)
        self.assertEqual(NODE_STATUS.ALLOCATED, node.status)

    def test_release(self):
        node = factory.make_node(
            status=NODE_STATUS.ALLOCATED, owner=factory.make_user())
        node.release()
        self.assertEqual((NODE_STATUS.READY, None), (node.status, node.owner))


class NodeManagerTest(TestCase):

    def make_node(self, user=None):
        """Create a node, allocated to `user` if given."""
        if user is None:
            status = NODE_STATUS.READY
        else:
            status = NODE_STATUS.ALLOCATED
        return factory.make_node(set_hostname=True, status=status, owner=user)

    def make_user_data(self):
        """Create a blob of arbitrary user-data."""
        return factory.getRandomString().encode('ascii')

    def test_filter_by_ids_filters_nodes_by_ids(self):
        nodes = [factory.make_node() for counter in range(5)]
        ids = [node.system_id for node in nodes]
        selection = slice(1, 3)
        self.assertItemsEqual(
            nodes[selection],
            Node.objects.filter_by_ids(Node.objects.all(), ids[selection]))

    def test_filter_by_ids_with_empty_list_returns_empty(self):
        factory.make_node()
        self.assertItemsEqual(
            [], Node.objects.filter_by_ids(Node.objects.all(), []))

    def test_filter_by_ids_without_ids_returns_full(self):
        node = factory.make_node()
        self.assertItemsEqual(
            [node], Node.objects.filter_by_ids(Node.objects.all(), None))

    def test_get_visible_nodes_for_user_lists_visible_nodes(self):
        """get_visible_nodes lists the nodes a user has access to.

        When run for a regular user it returns unowned nodes, and nodes
        owned by that user.
        """
        user = factory.make_user()
        visible_nodes = [self.make_node(owner) for owner in [None, user]]
        self.make_node(factory.make_user())
        self.assertItemsEqual(
            visible_nodes, Node.objects.get_visible_nodes(user))

    def test_get_visible_nodes_admin_lists_all_nodes(self):
        admin = factory.make_admin()
        owners = [
            None,
            factory.make_user(),
            factory.make_admin(),
            admin,
            ]
        nodes = [self.make_node(owner) for owner in owners]
        self.assertItemsEqual(nodes, Node.objects.get_visible_nodes(admin))

    def test_get_visible_nodes_filters_by_id(self):
        user = factory.make_user()
        nodes = [self.make_node(user) for counter in range(5)]
        ids = [node.system_id for node in nodes]
        wanted_slice = slice(0, 3)
        self.assertItemsEqual(
            nodes[wanted_slice],
            Node.objects.get_visible_nodes(user, ids=ids[wanted_slice]))

    def test_get_editable_nodes_for_user_lists_owned_nodes(self):
        user = factory.make_user()
        visible_node = self.make_node(user)
        self.make_node(None)
        self.make_node(factory.make_user())
        self.assertItemsEqual(
            [visible_node], Node.objects.get_editable_nodes(user))

    def test_get_editable_nodes_admin_lists_all_nodes(self):
        admin = factory.make_admin()
        owners = [
            None,
            factory.make_user(),
            factory.make_admin(),
            admin,
            ]
        nodes = [self.make_node(owner) for owner in owners]
        self.assertItemsEqual(nodes, Node.objects.get_editable_nodes(admin))

    def test_get_editable_nodes_filters_by_id(self):
        user = factory.make_user()
        nodes = [self.make_node(user) for counter in range(5)]
        ids = [node.system_id for node in nodes]
        wanted_slice = slice(0, 3)
        self.assertItemsEqual(
            nodes[wanted_slice],
            Node.objects.get_editable_nodes(user, ids=ids[wanted_slice]))

    def test_get_visible_node_or_404_ok(self):
        """get_visible_node_or_404 fetches nodes by system_id."""
        user = factory.make_user()
        node = self.make_node(user)
        self.assertEqual(
            node, Node.objects.get_visible_node_or_404(node.system_id, user))

    def test_get_visible_node_or_404_raises_PermissionDenied(self):
        """get_visible_node_or_404 raises PermissionDenied if the provided
        user cannot access the returned node."""
        user_node = self.make_node(factory.make_user())
        self.assertRaises(
            PermissionDenied,
            Node.objects.get_visible_node_or_404,
            user_node.system_id, factory.make_user())

    def test_get_available_node_for_acquisition_finds_available_node(self):
        user = factory.make_user()
        node = self.make_node(None)
        self.assertEqual(
            node, Node.objects.get_available_node_for_acquisition(user))

    def test_get_available_node_for_acquisition_returns_none_if_empty(self):
        user = factory.make_user()
        self.assertEqual(
            None, Node.objects.get_available_node_for_acquisition(user))

    def test_get_available_node_for_acquisition_ignores_taken_nodes(self):
        user = factory.make_user()
        available_status = NODE_STATUS.READY
        unavailable_statuses = (
            set(NODE_STATUS_CHOICES_DICT) - set([available_status]))
        for status in unavailable_statuses:
            factory.make_node(status=status)
        self.assertEqual(
            None, Node.objects.get_available_node_for_acquisition(user))

    def test_get_available_node_for_acquisition_ignores_invisible_nodes(self):
        user = factory.make_user()
        node = self.make_node()
        node.owner = factory.make_user()
        node.save()
        self.assertEqual(
            None, Node.objects.get_available_node_for_acquisition(user))

    def test_stop_nodes_stops_nodes(self):
        user = factory.make_user()
        node = self.make_node(user)
        output = Node.objects.stop_nodes([node.system_id], user)

        self.assertItemsEqual([node], output)
        power_status = get_provisioning_api_proxy().power_status
        self.assertEqual('stop', power_status[node.system_id])

    def test_stop_nodes_ignores_uneditable_nodes(self):
        nodes = [self.make_node(factory.make_user()) for counter in range(3)]
        ids = [node.system_id for node in nodes]
        stoppable_node = nodes[0]
        self.assertItemsEqual(
            [stoppable_node],
            Node.objects.stop_nodes(ids, stoppable_node.owner))

    def test_start_nodes_starts_nodes(self):
        user = factory.make_user()
        node = self.make_node(user)
        output = Node.objects.start_nodes([node.system_id], user)

        self.assertItemsEqual([node], output)
        power_status = get_provisioning_api_proxy().power_status
        self.assertEqual('start', power_status[node.system_id])

    def test_start_nodes_ignores_uneditable_nodes(self):
        nodes = [self.make_node(factory.make_user()) for counter in range(3)]
        ids = [node.system_id for node in nodes]
        startable_node = nodes[0]
        self.assertItemsEqual(
            [startable_node],
            Node.objects.start_nodes(ids, startable_node.owner))

    def test_start_nodes_stores_user_data(self):
        node = factory.make_node(owner=factory.make_user())
        user_data = self.make_user_data()
        Node.objects.start_nodes(
            [node.system_id], node.owner, user_data=user_data)
        self.assertEqual(user_data, NodeUserData.objects.get_user_data(node))

    def test_start_nodes_does_not_store_user_data_for_uneditable_nodes(self):
        node = factory.make_node(owner=factory.make_user())
        original_user_data = self.make_user_data()
        NodeUserData.objects.set_user_data(node, original_user_data)
        Node.objects.start_nodes(
            [node.system_id], factory.make_user(),
            user_data=self.make_user_data())
        self.assertEqual(
            original_user_data, NodeUserData.objects.get_user_data(node))

    def test_start_nodes_without_user_data_leaves_existing_data_alone(self):
        node = factory.make_node(owner=factory.make_user())
        user_data = self.make_user_data()
        NodeUserData.objects.set_user_data(node, user_data)
        Node.objects.start_nodes([node.system_id], node.owner, user_data=None)
        self.assertEqual(user_data, NodeUserData.objects.get_user_data(node))

    def test_start_nodes_with_user_data_overwrites_existing_data(self):
        node = factory.make_node(owner=factory.make_user())
        NodeUserData.objects.set_user_data(node, self.make_user_data())
        user_data = self.make_user_data()
        Node.objects.start_nodes(
            [node.system_id], node.owner, user_data=user_data)
        self.assertEqual(user_data, NodeUserData.objects.get_user_data(node))


class MACAddressTest(TestCase):

    def make_MAC(self, address):
        """Create a MAC address."""
        node = factory.make_node()
        return MACAddress(mac_address=address, node=node)

    def test_stores_to_database(self):
        mac = self.make_MAC('00:11:22:33:44:55')
        mac.save()
        self.assertEqual([mac], list(MACAddress.objects.all()))

    def test_invalid_address_raises_validation_error(self):
        mac = self.make_MAC('aa:bb:ccxdd:ee:ff')
        self.assertRaises(ValidationError, mac.full_clean)


class AuthTokensTest(TestCase):
    """Test creation and retrieval of auth tokens."""

    def assertTokenValid(self, token):
        self.assertIsInstance(token.key, basestring)
        self.assertEqual(KEY_SIZE, len(token.key))
        self.assertIsInstance(token.secret, basestring)
        self.assertEqual(SECRET_SIZE, len(token.secret))

    def assertConsumerValid(self, consumer):
        self.assertIsInstance(consumer.key, basestring)
        self.assertEqual(KEY_SIZE, len(consumer.key))
        self.assertEqual('', consumer.secret)

    def test_create_auth_token(self):
        user = factory.make_user()
        token = create_auth_token(user)
        self.assertEqual(user, token.user)
        self.assertEqual(user, token.consumer.user)
        self.assertTrue(token.is_approved)
        self.assertConsumerValid(token.consumer)
        self.assertTokenValid(token)

    def test_get_auth_tokens_finds_tokens_for_user(self):
        user = factory.make_user()
        token = create_auth_token(user)
        self.assertIn(token, get_auth_tokens(user))

    def test_get_auth_tokens_ignores_other_users(self):
        user, other_user = factory.make_user(), factory.make_user()
        unrelated_token = create_auth_token(other_user)
        self.assertNotIn(unrelated_token, get_auth_tokens(user))

    def test_get_auth_tokens_ignores_unapproved_tokens(self):
        user = factory.make_user()
        token = create_auth_token(user)
        token.is_approved = False
        token.save()
        self.assertNotIn(token, get_auth_tokens(user))


class UserProfileTest(TestCase):

    def test_profile_creation(self):
        # A profile is created each time a user is created.
        user = factory.make_user()
        self.assertIsInstance(user.get_profile(), UserProfile)
        self.assertEqual(user, user.get_profile().user)

    def test_consumer_creation(self):
        # A generic consumer is created each time a user is created.
        user = factory.make_user()
        consumers = Consumer.objects.filter(user=user, name=GENERIC_CONSUMER)
        self.assertEqual([user], [consumer.user for consumer in consumers])

    def test_token_creation(self):
        # A token is created each time a user is created.
        user = factory.make_user()
        [token] = get_auth_tokens(user)
        self.assertEqual(user, token.user)

    def test_create_authorisation_token(self):
        # UserProfile.create_authorisation_token calls create_auth_token.
        user = factory.make_user()
        profile = user.get_profile()
        consumer, token = profile.create_authorisation_token()
        self.assertEqual(user, token.user)
        self.assertEqual(user, consumer.user)

    def test_get_authorisation_tokens(self):
        # UserProfile.get_authorisation_tokens calls get_auth_tokens.
        user = factory.make_user()
        consumer, token = user.get_profile().create_authorisation_token()
        self.assertIn(token, user.get_profile().get_authorisation_tokens())

    def test_delete(self):
        # Deleting a profile also deletes the related user.
        profile = factory.make_user().get_profile()
        profile_id = profile.id
        user_id = profile.user.id
        self.assertTrue(User.objects.filter(id=user_id).exists())
        self.assertTrue(
            UserProfile.objects.filter(id=profile_id).exists())
        profile.delete()
        self.assertFalse(User.objects.filter(id=user_id).exists())
        self.assertFalse(
            UserProfile.objects.filter(id=profile_id).exists())

    def test_delete_consumers_tokens(self):
        # Deleting a profile deletes the related tokens and consumers.
        profile = factory.make_user().get_profile()
        token_ids = []
        consumer_ids = []
        for i in range(3):
            token, consumer = profile.create_authorisation_token()
            token_ids.append(token.id)
            consumer_ids.append(consumer.id)
        profile.delete()
        self.assertFalse(Consumer.objects.filter(id__in=consumer_ids).exists())
        self.assertFalse(Token.objects.filter(id__in=token_ids).exists())

    def test_delete_attached_nodes(self):
        # Cannot delete a user with nodes attached to it.
        profile = factory.make_user().get_profile()
        factory.make_node(owner=profile.user)
        self.assertRaises(CannotDeleteUserException, profile.delete)

    def test_manager_all_users(self):
        users = set(factory.make_user() for i in range(3))
        all_users = set(UserProfile.objects.all_users())
        self.assertEqual(users, all_users)

    def test_manager_all_users_no_system_user(self):
        for i in range(3):
            factory.make_user()
        usernames = set(
            user.username for user in UserProfile.objects.all_users())
        self.assertTrue(set(SYSTEM_USERS).isdisjoint(usernames))


class SSHKeyManagerTest(TestCase):
    """Testing for the :class `SSHKeyManager` model manager."""

    def test_get_keys_for_user_no_keys(self):
        user = factory.make_user()
        keys = SSHKey.objects.get_keys_for_user(user)
        self.assertItemsEqual([], keys)

    def test_get_keys_for_user_with_keys(self):
        user1 = factory.make_user_with_keys(n_keys=3, username='user1')
        # user2
        factory.make_user_with_keys(n_keys=2)
        keys = SSHKey.objects.get_keys_for_user(user1)
        self.assertItemsEqual([
            'ssh-rsa KEY user1-key-0',
            'ssh-rsa KEY user1-key-1',
            'ssh-rsa KEY user1-key-2',
            ], keys)


class FileStorageTest(TestCase):
    """Testing of the :class:`FileStorage` model."""

    def make_upload_dir(self):
        """Create the upload directory, and arrange for eventual deletion.

        The directory must not already exist.  If it does, this method will
        fail rather than arrange for deletion of a directory that may
        contain meaningful data.

        :return: Absolute path to the `FileStorage` upload directory.  This
            is the directory where the actual files are stored.
        """
        media_root = settings.MEDIA_ROOT
        self.assertFalse(os.path.exists(media_root), "See media/README")
        self.addCleanup(shutil.rmtree, media_root, ignore_errors=True)
        os.mkdir(media_root)
        upload_dir = os.path.join(media_root, FileStorage.upload_dir)
        os.mkdir(upload_dir)
        return upload_dir

    def get_media_path(self, filename):
        """Get the path to a given stored file, relative to MEDIA_ROOT."""
        return os.path.join(FileStorage.upload_dir, filename)

    def make_data(self, including_text='data'):
        """Return arbitrary data.

        :param including_text: Text to include in the data.  Leave something
            here to make failure messages more recognizable.
        :type including_text: basestring
        :return: A string of bytes, including `including_text`.
        :rtype: bytes
        """
        # Note that this won't automatically insert any non-ASCII bytes.
        # Proper handling of real binary data is tested separately.
        text = "%s %s" % (including_text, factory.getRandomString())
        return text.encode('ascii')

    def age_file(self, path, seconds=None):
        """Make the file at `path` look like it hasn't been touched recently.

        Decrements the file's mtime by a bit over a day.
        """
        if seconds is None:
            seconds = FileStorage.objects.grace_time + 1
        stat_result = os.stat(path)
        atime = stat_result.st_atime
        mtime = stat_result.st_mtime
        os.utime(path, (atime, mtime - seconds))

    def test_get_existing_storage_returns_None_if_none_found(self):
        nonexistent_file = factory.getRandomString()
        self.assertIsNone(
            FileStorage.objects.get_existing_storage(nonexistent_file))

    def test_get_existing_storage_finds_FileStorage(self):
        self.make_upload_dir()
        storage = factory.make_file_storage()
        self.assertEqual(
            storage,
            FileStorage.objects.get_existing_storage(storage.filename))

    def test_save_file_creates_storage(self):
        self.make_upload_dir()
        filename = factory.getRandomString()
        data = self.make_data()
        storage = FileStorage.objects.save_file(filename, BytesIO(data))
        self.assertEqual(
            (filename, data),
            (storage.filename, storage.data.read()))

    def test_storage_can_be_retrieved(self):
        self.make_upload_dir()
        filename = factory.getRandomString()
        data = self.make_data()
        factory.make_file_storage(filename=filename, data=data)
        storage = FileStorage.objects.get(filename=filename)
        self.assertEqual(
            (filename, data),
            (storage.filename, storage.data.read()))

    def test_stores_binary_data(self):
        self.make_upload_dir()

        # This horrible binary data could never, ever, under any
        # encoding known to man be interpreted as text(1).  Switch the
        # bytes of the byte-order mark around and by design you get an
        # invalid codepoint; put a byte with the high bit set between bytes
        # that have it cleared, and you have a guaranteed non-UTF-8
        # sequence.
        #
        # (1) Provided, of course, that man know only about ASCII and
        # UTF.
        binary_data = codecs.BOM64_LE + codecs.BOM64_BE + b'\x00\xff\x00'

        # And yet, because FileStorage supports binary data, it comes
        # out intact.
        storage = factory.make_file_storage(filename="x", data=binary_data)
        self.assertEqual(binary_data, storage.data.read())

    def test_overwrites_file(self):
        # If a file of the same name has already been stored, the
        # reference to the old data gets overwritten with one to the new
        # data.  They are actually different files on the filesystem.
        self.make_upload_dir()
        filename = 'filename-%s' % factory.getRandomString()
        old_storage = factory.make_file_storage(
            filename=filename, data=self.make_data('old data'))
        new_data = self.make_data('new-data')
        new_storage = factory.make_file_storage(
            filename=filename, data=new_data)
        self.assertNotEqual(old_storage.data.name, new_storage.data.name)
        self.assertEqual(
            new_data, FileStorage.objects.get(filename=filename).data.read())

    def test_list_stored_files_lists_files(self):
        upload_dir = self.make_upload_dir()
        filename = factory.getRandomString()
        with open(os.path.join(upload_dir, filename), 'w') as f:
            f.write(self.make_data())
        self.assertIn(
            self.get_media_path(filename),
            FileStorage.objects.list_stored_files())

    def test_list_stored_files_includes_referenced_files(self):
        self.make_upload_dir()
        storage = factory.make_file_storage()
        self.assertIn(
            storage.data.name, FileStorage.objects.list_stored_files())

    def test_list_referenced_files_lists_FileStorage_files(self):
        self.make_upload_dir()
        storage = factory.make_file_storage()
        self.assertIn(
            storage.data.name, FileStorage.objects.list_referenced_files())

    def test_list_referenced_files_excludes_unreferenced_files(self):
        upload_dir = self.make_upload_dir()
        filename = factory.getRandomString()
        with open(os.path.join(upload_dir, filename), 'w') as f:
            f.write(self.make_data())
        self.assertNotIn(
            self.get_media_path(filename),
            FileStorage.objects.list_referenced_files())

    def test_list_referenced_files_uses_file_name_not_FileStorage_name(self):
        self.make_upload_dir()
        filename = factory.getRandomString()
        # The filename we're going to use is already taken.  The file
        # we'll be looking at will have to have a different name.
        factory.make_file_storage(filename=filename)
        storage = factory.make_file_storage(filename=filename)
        # It's the name of the file, not the FileStorage.filename, that
        # is in list_referenced_files.
        self.assertIn(
            storage.data.name, FileStorage.objects.list_referenced_files())

    def test_is_old_returns_False_for_recent_file(self):
        upload_dir = self.make_upload_dir()
        filename = factory.getRandomString()
        path = os.path.join(upload_dir, filename)
        with open(path, 'w') as f:
            f.write(self.make_data())
        self.age_file(path, FileStorage.objects.grace_time - 60)
        self.assertFalse(
            FileStorage.objects.is_old(self.get_media_path(filename)))

    def test_is_old_returns_True_for_old_file(self):
        upload_dir = self.make_upload_dir()
        filename = factory.getRandomString()
        path = os.path.join(upload_dir, filename)
        with open(path, 'w') as f:
            f.write(self.make_data())
        self.age_file(path, FileStorage.objects.grace_time + 1)
        self.assertTrue(
            FileStorage.objects.is_old(self.get_media_path(filename)))

    def test_collect_garbage_deletes_garbage(self):
        upload_dir = self.make_upload_dir()
        filename = factory.getRandomString()
        path = os.path.join(upload_dir, filename)
        with open(path, 'w') as f:
            f.write(self.make_data())
        self.age_file(path)
        FileStorage.objects.collect_garbage()
        self.assertFalse(
            FileStorage.storage.exists(self.get_media_path(filename)))

    def test_grace_time_is_generous_but_not_unlimited(self):
        # Grace time for garbage collection is long enough that it won't
        # expire while the request that wrote it is still being handled.
        # But it won't keep a file around for ages.  For instance, it'll
        # be more than 20 seconds, but less than a day.
        self.assertThat(FileStorage.objects.grace_time, GreaterThan(20))
        self.assertThat(FileStorage.objects.grace_time, LessThan(24 * 60 * 60))

    def test_collect_garbage_leaves_recent_files_alone(self):
        upload_dir = self.make_upload_dir()
        filename = factory.getRandomString()
        with open(os.path.join(upload_dir, filename), 'w') as f:
            f.write(self.make_data())
        FileStorage.objects.collect_garbage()
        self.assertTrue(
            FileStorage.storage.exists(self.get_media_path(filename)))

    def test_collect_garbage_leaves_referenced_files_alone(self):
        self.make_upload_dir()
        storage = factory.make_file_storage()
        self.age_file(storage.data.path)
        FileStorage.objects.collect_garbage()
        self.assertTrue(FileStorage.storage.exists(storage.data.name))

    def test_collect_garbage_tolerates_missing_upload_dir(self):
        # When MAAS is freshly installed, the upload directory is still
        # missing.  But...
        FileStorage.objects.collect_garbage()
        # ...we get through garbage collection without breakage.
        pass


class ConfigDefaultTest(TestCase, TestWithFixtures):
    """Test config default values."""

    def test_default_config_maas_name(self):
        default_config = get_default_config()
        self.assertEqual(gethostname(), default_config['maas_name'])


class Listener:
    """A utility class which tracks the calls to its 'call' method and
    stores the arguments given to 'call' in 'self.calls'.
    """

    def __init__(self):
        self.calls = []

    def call(self, *args, **kwargs):
        self.calls.append([args, kwargs])


class ConfigTest(TestCase):
    """Testing of the :class:`Config` model and its related manager class."""

    def test_manager_get_config_found(self):
        Config.objects.create(name='name', value='config')
        config = Config.objects.get_config('name')
        self.assertEqual('config', config)

    def test_manager_get_config_not_found(self):
        config = Config.objects.get_config('name', 'default value')
        self.assertEqual('default value', config)

    def test_manager_get_config_not_found_none(self):
        config = Config.objects.get_config('name')
        self.assertIsNone(config)

    def test_manager_get_config_not_found_in_default_config(self):
        name = factory.getRandomString()
        value = factory.getRandomString()
        DEFAULT_CONFIG[name] = value
        config = Config.objects.get_config(name, None)
        self.assertEqual(value, config)

    def test_default_config_cannot_be_changed(self):
        name = factory.getRandomString()
        DEFAULT_CONFIG[name] = {'key': 'value'}
        config = Config.objects.get_config(name)
        config.update({'key2': 'value2'})

        self.assertEqual({'key': 'value'}, Config.objects.get_config(name))

    def test_manager_get_config_list_returns_config_list(self):
        Config.objects.create(name='name', value='config1')
        Config.objects.create(name='name', value='config2')
        config_list = Config.objects.get_config_list('name')
        self.assertItemsEqual(['config1', 'config2'], config_list)

    def test_manager_set_config_creates_config(self):
        Config.objects.set_config('name', 'config1')
        Config.objects.set_config('name', 'config2')
        self.assertSequenceEqual(
            ['config2'],
            [config.value for config in Config.objects.filter(name='name')])

    def test_manager_config_changed_connect_connects(self):
        listener = Listener()
        name = factory.getRandomString()
        value = factory.getRandomString()
        Config.objects.config_changed_connect(name, listener.call)
        Config.objects.set_config(name, value)
        config = Config.objects.get(name=name)

        self.assertEqual(1, len(listener.calls))
        self.assertEqual((Config, config, True), listener.calls[0][0])

    def test_manager_config_changed_connect_connects_multiple(self):
        listener = Listener()
        listener2 = Listener()
        name = factory.getRandomString()
        value = factory.getRandomString()
        Config.objects.config_changed_connect(name, listener.call)
        Config.objects.config_changed_connect(name, listener2.call)
        Config.objects.set_config(name, value)

        self.assertEqual(1, len(listener.calls))
        self.assertEqual(1, len(listener2.calls))

    def test_manager_config_changed_connect_connects_multiple_same(self):
        # If the same method is connected twice, it will only get called
        # once.
        listener = Listener()
        name = factory.getRandomString()
        value = factory.getRandomString()
        Config.objects.config_changed_connect(name, listener.call)
        Config.objects.config_changed_connect(name, listener.call)
        Config.objects.set_config(name, value)

        self.assertEqual(1, len(listener.calls))

    def test_manager_config_changed_connect_connects_by_config_name(self):
        listener = Listener()
        name = factory.getRandomString()
        value = factory.getRandomString()
        Config.objects.config_changed_connect(name, listener.call)
        another_name = factory.getRandomString()
        Config.objects.set_config(another_name, value)

        self.assertEqual(0, len(listener.calls))
