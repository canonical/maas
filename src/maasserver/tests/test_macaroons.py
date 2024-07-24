#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from unittest import TestCase

from macaroonbakery.bakery import IdentityError

from maasserver.macaroons import _get_authentication_caveat, _IDClient
from maasserver.testing.testcase import MAASServerTestCase


class TestIDClient(MAASServerTestCase):
    def setUp(self):
        super().setUp()
        self.client = _IDClient("https://example.com")

    def test_declared_entity(self):
        identity = self.client.declared_identity(None, {"username": "user"})
        self.assertEqual(identity.id(), "user")

    def test_declared_entity_no_username(self):
        self.assertRaises(
            IdentityError,
            self.client.declared_identity,
            None,
            {"other": "stuff"},
        )

    def test_identity_from_context(self):
        _, [caveat] = self.client.identity_from_context(None)
        self.assertEqual(caveat.location, "https://example.com")
        self.assertEqual(caveat.condition, "is-authenticated-user")

    def test_identity_from_context_with_domain(self):
        client = _IDClient("https://example.com", auth_domain="mydomain")
        _, [caveat] = client.identity_from_context(None)
        self.assertEqual(caveat.location, "https://example.com")
        self.assertEqual(caveat.condition, "is-authenticated-user @mydomain")


class TestGetAuthenticationCaveat(TestCase):
    def test_caveat(self):
        caveat = _get_authentication_caveat(
            "https://example.com", domain="mydomain"
        )
        self.assertEqual(caveat.location, "https://example.com")
        self.assertEqual(caveat.condition, "is-authenticated-user @mydomain")

    def test_caveat_no_domain(self):
        caveat = _get_authentication_caveat("https://example.com")
        self.assertEqual(caveat.location, "https://example.com")
        self.assertEqual(caveat.condition, "is-authenticated-user")

    def test_caveat_empty_domain(self):
        caveat = _get_authentication_caveat("https://example.com", domain="")
        self.assertEqual(caveat.location, "https://example.com")
        self.assertEqual(caveat.condition, "is-authenticated-user")
