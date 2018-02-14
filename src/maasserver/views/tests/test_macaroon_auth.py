# Copyright 2018 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from datetime import (
    datetime,
    timedelta,
)
from unittest import TestCase

from maasserver.models import (
    Config,
    RootKey,
)
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.views.macaroon_auth import (
    _get_macaroon_oven_key,
    IDClient,
    KeyStore,
    MacaroonAuthenticationBackend,
)
from macaroonbakery.bakery import (
    IdentityError,
    SimpleIdentity,
)


class TestIDClient(TestCase):

    def setUp(self):
        super().setUp()
        self.client = IDClient('https://example.com')

    def test_declared_entity(self):
        identity = self.client.declared_identity(None, {'username': 'user'})
        self.assertEqual(identity.id(), 'user')

    def test_declared_entity_no_username(self):
        with self.assertRaises(IdentityError) as cm:
            self.client.declared_identity(None, {'other': 'stuff'})
        self.assertEqual(str(cm.exception), 'No username found')

    def test_identity_from_context(self):
        _, [caveat] = self.client.identity_from_context(None)
        self.assertEqual(caveat.location, 'https://example.com')
        self.assertEqual(caveat.condition, 'is-authenticated-user')


class TestMacaroonAuthenticationBackend(MAASServerTestCase):

    def test_authenticate(self):
        user = factory.make_User()
        backend = MacaroonAuthenticationBackend()
        identity = SimpleIdentity(user=user.username)
        self.assertEqual(backend.authenticate(identity), user)

    def test_authenticate_unknown_user(self):
        backend = MacaroonAuthenticationBackend()
        identity = SimpleIdentity(user='unknown')
        self.assertIsNone(backend.authenticate(identity))


class TestMacaroonOvenKey(MAASServerTestCase):

    def test__get_macaroon_oven_key(self):
        key = _get_macaroon_oven_key()
        self.assertEqual(
            Config.objects.get_config('macaroon_private_key'),
            key.serialize().decode('ascii'))

    def test__get_macaroon_oven_key_existing(self):
        key = _get_macaroon_oven_key()
        self.assertEqual(_get_macaroon_oven_key(), key)


class TestKeyStore(MAASServerTestCase):

    def setUp(self):
        super().setUp()
        self.expiry_duration = timedelta(hours=4)
        self.generate_interval = timedelta(hours=1)
        self.now = datetime.now()
        self.store = KeyStore(
            self.expiry_duration, generate_interval=self.generate_interval,
            now=lambda: self.now)

    def test_intervals(self):
        self.assertEqual(self.store.expiry_duration, self.expiry_duration)
        self.assertEqual(self.store.generate_interval, self.generate_interval)

    def test_generate_interval_default(self):
        interval = timedelta(hours=1)
        store = KeyStore(interval)
        self.assertEqual(store.generate_interval, interval)

    def test_root_key(self):
        material, key_id = self.store.root_key()
        key = RootKey.objects.get(pk=int(key_id))
        self.assertEqual(key.material.tobytes(), material)
        self.assertEqual(
            key.expiration,
            self.now + self.expiry_duration + self.generate_interval)

    def test_root_key_reuse_existing(self):
        material1, key_id1 = self.store.root_key()
        # up to the generate interval, the same key is reused
        self.now += self.generate_interval
        material2, key_id2 = self.store.root_key()
        self.assertEqual(key_id1, key_id2)
        self.assertEqual(material1, material2)

    def test_root_key_new_key_after_interval(self):
        material1, key_id1 = self.store.root_key()
        self.now += self.generate_interval + timedelta(seconds=1)
        material2, key_id2 = self.store.root_key()
        self.assertNotEqual(key_id1, key_id2)
        self.assertNotEqual(material1, material2)

    def test_root_key_expired_ignored(self):
        _, key_id1 = self.store.root_key()
        key = RootKey.objects.first()
        key.expiration = self.now - timedelta(days=1)
        key.save()
        _, key_id2 = self.store.root_key()
        # a new key is created since one is expired
        self.assertNotEqual(key_id2, key_id1)

    def test_root_key_expired_removed(self):
        factory.make_RootKey(expiration=self.now - timedelta(days=1))
        factory.make_RootKey(expiration=self.now - timedelta(days=2))
        _, key_id = self.store.root_key()
        # expired keys have been removed
        self.assertCountEqual(
            [(int(key_id),)], RootKey.objects.values_list('id'))

    def test_get(self):
        material, key_id = self.store.root_key()
        self.assertEqual(self.store.get(key_id), material)

    def test_get_expired(self):
        _, key_id = self.store.root_key()
        key = RootKey.objects.get(pk=int(key_id))
        # expire the key
        key.expiration = self.now - timedelta(days=1)
        key.save()
        self.assertIsNone(self.store.get(key_id))

    def test_get_not_found(self):
        self.assertIsNone(self.store.get(b'-1'))

    def test_get_not_found_id_not_numeric(self):
        self.assertIsNone(self.store.get(b'invalid'))
