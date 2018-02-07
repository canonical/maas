# Copyright 2018 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from unittest import TestCase

from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.views.macaroon_auth import (
    IDClient,
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
